# Energy Price Intelligence — VIC1 (Victoria, Australia)

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3FCF8E?style=for-the-badge&logo=supabase&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-006ACC?style=for-the-badge&logo=xgboost&logoColor=white)
![Power BI](https://img.shields.io/badge/Power_BI-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

🔗 **[Live Dashboard](https://energy-price-intelligence-vic1-by-khoshaba.streamlit.app/)**

A production-style data pipeline forecasting and monitoring electricity spot price risk for Victoria's National Electricity Market (NEM) region, built end-to-end: Supabase → SQL analysis → feature engineering → XGBoost → Power BI → Docker.

**Author:** Khoshaba Odeesho | Assyrian AI | Melbourne, Australia

---

## What this project does

- Ingests 13 months (Jun 2025 – Jun 2026) of 5-minute AEMO price/demand data for VIC1, plus hourly Melbourne temperature (Open-Meteo)
- Loads and models the data in Supabase (Postgres), with a SQL view (`energy_features`) doing all feature engineering
- Trains two XGBoost classifiers to predict price spikes (RRP > $300/MWh):
  - **Live Risk model** — uses recent price history, strong nowcasting signal
  - **Forecast-only model** — uses only calendar/demand/weather features, tests genuine advance prediction
- Visualizes findings in a 3-page Power BI dashboard
- Runs the pipeline in Docker for environment-independent reproducibility

---

## Results & Limitations (read this before trusting the dashboard)

| Component | Status |
|---|---|
| Live risk indicator (lag-based model) | ✅ AUC 0.998 — strong for detecting an in-progress spike |
| Historical pattern insights | ✅ Validated in SQL — duck-curve (5–8pm peak), June 2025 outage event, demand correlation |
| Day-ahead spike forecasting | ⚠️ Tested with calendar + demand + temperature features. AUC capped around 0.94–0.95, but unusable precision (best case ~5%) at any confidence threshold. |

**Why day-ahead forecasting falls short:** 83% of the live model's predictive power comes from the previous 5-minute price (`rrp_prev_interval`) — this is closer to nowcasting than forecasting. When that feature is removed and only forward-looking features remain, the model can still rank risk meaningfully above random (AUC ~0.94), but can't produce a usable number of true positives without an overwhelming number of false alarms. Adding Melbourne temperature data barely moved the needle (AUC 0.944 → 0.952), because temperature is largely redundant with `total_demand`, which the model already has.

**Most likely missing ingredient:** generation-side data — wind/solar output and scheduled generator outages — which are the actual physical drivers of most price spikes but aren't available in this dataset. Flagged as future work.

**A real, documented event validates this data:** June 2025 saw a genuine ~108% month-on-month price surge in Victoria, driven by coal plant outages. This project's data and SQL analysis independently reproduce that event (avg price $264.62 vs $27–93 in surrounding months), which is a strong sanity check that the pipeline reflects real market behavior, not synthetic noise.

---

## Tech stack

Python · Supabase (PostgreSQL) · SQL (window functions, views) · XGBoost · scikit-learn · pandas · Power BI · Docker · Open-Meteo API · AEMO public data

---

## Data sources

- **AEMO** — [Aggregated price and demand data](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/aggregated-data), VIC1 region, 5-minute resolution
- **Open-Meteo** — free historical weather archive, Melbourne CBD (-37.8136, 144.9631), hourly temperature

---

## Repo structure

```
├── data/            # merged AEMO CSV
├── scripts/         # ingestion, loading, training pipeline
├── models/          # trained XGBoost models (.json)
├── dashboard/        # Power BI file + PDF export
├── screenshots/      # dashboard screenshots
├── Dockerfile
├── .dockerignore
├── requirements.txt
└── .env.example      # copy to .env and fill in your own Supabase credentials
```

---

## Running it yourself

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up credentials
cp .env.example .env   # then fill in your own Supabase connection details

# 3. Load data
python scripts/load_to_supabase.py

# 4. Fetch weather (optional feature)
python scripts/fetch_weather.py

# 5. Train models
python scripts/train_model.py
python scripts/train_model_forecast_only.py

# 6. Or run via Docker (no local Python setup needed)
docker build -t energy-pipeline .
docker run --env-file .env energy-pipeline
docker run --env-file .env energy-pipeline python scripts/train_model.py
```

---

## Dashboard

See `dashboard/energy-price-intelligence-vic1.pdf` for a static preview, or open the `.pbix` in Power BI Desktop (connect to your own Supabase instance via `.env` credentials).

Three pages: **Overview** (KPIs + monthly trend), **Spike Analysis** (hour-of-day duck curve, demand correlation, monthly spike count), **Model Insights** (feature importance, honest limitations).

---

*Part of the Assyrian AI portfolio — [github.com/Assyrian91](https://github.com/Assyrian91)*
