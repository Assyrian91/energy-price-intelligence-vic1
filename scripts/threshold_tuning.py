"""
Sweep decision thresholds on the forecast-only model to find a usable
precision/recall tradeoff instead of the default (often wrong) 0.5 cutoff.
Run this AFTER train_model_forecast_only.py has produced spike_model_forecast_only.json.
"""
import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from sklearn.metrics import precision_score, recall_score
from xgboost import XGBClassifier

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"], port=os.environ["DB_PORT"], dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
    )

df = pd.read_sql("SELECT * FROM energy_features;", get_connection())
df["settlement_date"] = pd.to_datetime(df["settlement_date"])
df = df.sort_values("settlement_date").reset_index(drop=True).dropna(subset=["rrp_prev_interval", "temperature_2m"])

split_date = "2026-05-01"
train = df[df["settlement_date"] < split_date]
test = df[df["settlement_date"] >= split_date]

feature_cols = ["total_demand", "hour_of_day", "month_num", "is_peak_hour",
                 "is_known_outage_period", "temperature_2m", "is_temp_extreme"]
cat_cols = ["day_type", "season"]
train_X = pd.get_dummies(train[feature_cols + cat_cols], columns=cat_cols)
test_X = pd.get_dummies(test[feature_cols + cat_cols], columns=cat_cols)
test_X = test_X.reindex(columns=train_X.columns, fill_value=0)
train_y, test_y = train["is_spike"], test["is_spike"]

model = XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.05,
                       scale_pos_weight=(train_y == 0).sum() / (train_y == 1).sum(),
                       eval_metric="logloss", random_state=42)
model.fit(train_X, train_y)
proba = model.predict_proba(test_X)[:, 1]

print(f"{'Threshold':>10} {'Precision':>10} {'Recall':>10} {'Alerts':>8} {'Caught':>8}")
for t in [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]:
    pred = (proba >= t).astype(int)
    p = precision_score(test_y, pred, zero_division=0)
    r = recall_score(test_y, pred, zero_division=0)
    print(f"{t:>10.2f} {p:>10.3f} {r:>10.3f} {pred.sum():>8} {int((pred & test_y).sum()):>8}")