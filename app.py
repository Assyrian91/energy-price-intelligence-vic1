"""
Energy Price Intelligence — VIC1
Streamlit dashboard: KPIs, price trend, duck curve, and a live spike-risk
indicator using the trained XGBoost model.

Run: streamlit run app.py
Needs the same .env used by the pipeline scripts (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD).
"""
import os
import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from xgboost import XGBClassifier

load_dotenv()

st.set_page_config(
    page_title="Energy Price Intelligence — VIC1",
    page_icon="⚡",
    layout="wide",
)

# ---------- Theme (matches the Power BI dark navy / teal / red palette) ----------
st.markdown("""
<style>
.stApp { background-color: #0F172A; color: #E2E8F0; }
[data-testid="stMetricValue"] { color: #22D3EE; }
[data-testid="stMetricLabel"] { color: #94A3B8; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


@st.cache_data(ttl=3600)
def load_features():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM energy_features ORDER BY settlement_date;", conn)
    df["settlement_date"] = pd.to_datetime(df["settlement_date"])
    return df


@st.cache_resource
def load_model():
    model = XGBClassifier()
    model.load_model("models/spike_model.json")
    return model


# ---------- Load data ----------
with st.spinner("Loading data from Supabase..."):
    df = load_features()

# ---------- Header ----------
st.title("⚡ Energy Price Intelligence — VIC1")
st.caption("AEMO Victorian electricity spot price analysis · Jun 2025 – Jun 2026")

# ---------- KPI row ----------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Avg Price ($/MWh)", f"{df['rrp'].mean():.2f}")
col2.metric("Max Price ($/MWh)", f"{df['rrp'].max():,.0f}")
spike_count = int(df["is_spike"].sum())
col3.metric("Spike Count", spike_count, delta=None, delta_color="inverse")
col4.metric("Total Intervals", f"{len(df):,}")

st.divider()

# ---------- Price trend ----------
st.subheader("Monthly Average Price")
df["year_month"] = df["settlement_date"].dt.to_period("M").astype(str)
monthly = df[df["year_month"] != "2026-07"].groupby("year_month", as_index=False)["rrp"].mean()
fig_trend = px.line(monthly, x="year_month", y="rrp", markers=True)
fig_trend.update_traces(line_color="#22D3EE")
fig_trend.update_layout(
    plot_bgcolor="#0F172A", paper_bgcolor="#0F172A", font_color="#E2E8F0",
    xaxis_title="Month", yaxis_title="Avg Price ($/MWh)",
)
st.plotly_chart(fig_trend, use_container_width=True)
st.caption("June 2025 shows a documented ~108% price surge driven by coal plant outages — a real, verified market event, not a data artifact.")

st.divider()

# ---------- Duck curve + Live risk, side by side ----------
left, right = st.columns([1.3, 1])

with left:
    st.subheader("Average Price by Hour of Day")
    hourly = df.groupby("hour_of_day", as_index=False)["rrp"].mean()
    hourly["is_peak"] = hourly["hour_of_day"].between(17, 20)
    fig_hour = px.bar(hourly, x="hour_of_day", y="rrp", color="is_peak",
                       color_discrete_map={True: "#F87171", False: "#22D3EE"})
    fig_hour.update_layout(
        plot_bgcolor="#0F172A", paper_bgcolor="#0F172A", font_color="#E2E8F0",
        xaxis_title="Hour of day", yaxis_title="Avg Price ($/MWh)", showlegend=False,
    )
    st.plotly_chart(fig_hour, use_container_width=True)
    st.caption("Peak window (5–8pm, red) — Australia's 'duck curve': solar drops off as demand rises.")

with right:
    st.subheader("Live Spike Risk")
    st.caption("Model: XGBoost (AUC 0.998) · uses recent price trend — nowcasting, not day-ahead forecasting")

    latest = df.dropna(subset=["rrp_prev_interval"]).iloc[-1]

    # Debug: let you preview the gauge against a known historical spike moment
    if st.checkbox("🔧 Debug: preview a known spike interval instead of latest", value=False):
        spike_row = df[df["settlement_date"] == "2025-06-26 20:00:00"]
        if not spike_row.empty:
            latest = spike_row.iloc[0]

    model = load_model()

    feature_cols = ["total_demand", "hour_of_day", "month_num", "is_peak_hour",
                     "rrp_prev_interval", "rrp_rolling_1hr", "is_known_outage_period"]
    row = pd.DataFrame([latest[feature_cols]])
    for cat, val in [("day_type", latest["day_type"]), ("season", latest["season"])]:
        row[f"{cat}_{val}"] = 1
    # align to model's expected columns, fill missing dummies with 0
    for col in model.get_booster().feature_names:
        if col not in row.columns:
            row[col] = 0
    row = row[model.get_booster().feature_names]

    risk = model.predict_proba(row)[0][1]

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=risk * 100,
        number={"suffix": "%", "font": {"color": "#E2E8F0"}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#94A3B8"},
            "bar": {"color": "#F87171" if risk > 0.5 else "#22D3EE"},
            "bgcolor": "#1E293B",
            "steps": [
                {"range": [0, 30], "color": "#0F172A"},
                {"range": [30, 70], "color": "#1E293B"},
                {"range": [70, 100], "color": "#3F1D1D"},
            ],
        },
    ))
    fig_gauge.update_layout(paper_bgcolor="#0F172A", font_color="#E2E8F0", height=280)
    st.plotly_chart(fig_gauge, use_container_width=True)
    st.caption(f"Based on interval: {latest['settlement_date']} · Price at that time: ${latest['rrp']:.2f}/MWh")

st.divider()

# ---------- Limitations ----------
with st.expander("⚠️ Model Limitations — read before trusting this dashboard", expanded=False):
    st.markdown("""
    - **Live Risk model (AUC 0.998)** is strong for detecting an *in-progress* price spike,
      but 83% of its predictive power comes from the previous 5-minute price — this is
      **nowcasting, not advance forecasting**.
    - A genuine **day-ahead forecasting model** (using only calendar, demand, and temperature —
      features known in advance) was tested and achieved AUC 0.94–0.95, but could not reach
      usable precision at any confidence threshold (best case: ~5% precision).
    - **Likely missing ingredient:** generation-side data (wind/solar output, scheduled outages) —
      not available in this dataset. Flagged as future work.
    """)

st.caption("Built by Khoshaba Odeesho · Assyrian AI · [github.com/Assyrian91](https://github.com/Assyrian91)")