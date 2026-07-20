"""
Variant B: 'Genuine forecasting' test.
Removes rrp_prev_interval and rrp_rolling_1hr (the autocorrelation crutch) so the
model must learn real DRIVERS of spikes (time, demand, season) rather than just
detecting a spike that's already happening.

This is the honest test of whether the features we engineered actually predict
the future, or whether the first model was just noticing "it's already expensive."

Setup: same as train_model.py (uses the same .env)
"""
import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
from xgboost import XGBClassifier

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )

def load_features():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM energy_features;", conn)
    conn.close()
    return df

def main():
    print("Pulling energy_features from Supabase...")
    df = load_features()
    df["settlement_date"] = pd.to_datetime(df["settlement_date"])
    df = df.sort_values("settlement_date").reset_index(drop=True)
    df = df.dropna(subset=["rrp_prev_interval", "temperature_2m"])  # drop unusable rows

    split_date = "2026-05-01"
    train = df[df["settlement_date"] < split_date]
    test = df[df["settlement_date"] >= split_date]

    # --- KEY DIFFERENCE: no rrp_prev_interval, no rrp_rolling_1hr ---
    # Only features you'd genuinely know in advance (a weather/demand forecast, calendar)
    # NOW INCLUDES temperature — testing whether weather closes the forecasting gap
    feature_cols = ["total_demand", "hour_of_day", "month_num", "is_peak_hour",
                     "is_known_outage_period", "temperature_2m", "is_temp_extreme"]
    cat_cols = ["day_type", "season"]

    train_X = pd.get_dummies(train[feature_cols + cat_cols], columns=cat_cols)
    test_X = pd.get_dummies(test[feature_cols + cat_cols], columns=cat_cols)
    test_X = test_X.reindex(columns=train_X.columns, fill_value=0)

    train_y = train["is_spike"]
    test_y = test["is_spike"]

    print(f"\nFeatures used: {list(train_X.columns)}")
    print("(No lag or rolling price features — this model can't lean on 'already expensive')")

    model = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        scale_pos_weight=(train_y == 0).sum() / (train_y == 1).sum(),
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(train_X, train_y)

    pred = model.predict(test_X)
    pred_proba = model.predict_proba(test_X)[:, 1]

    print("\n--- Classification report (forecast-only model, no lag features) ---")
    print(classification_report(test_y, pred, digits=3))
    print(f"ROC-AUC: {roc_auc_score(test_y, pred_proba):.4f}")

    cm = confusion_matrix(test_y, pred)
    print("\n--- Confusion matrix ---")
    print(f"                 Predicted No-Spike   Predicted Spike")
    print(f"Actual No-Spike        {cm[0][0]:>6}              {cm[0][1]:>6}")
    print(f"Actual Spike           {cm[1][0]:>6}              {cm[1][1]:>6}")

    print("\n--- Feature importance (forecast-only) ---")
    importances = pd.Series(model.feature_importances_, index=train_X.columns).sort_values(ascending=False)
    print(importances.to_string())

    model.save_model("spike_model_forecast_only.json")
    print("\nModel saved to spike_model_forecast_only.json")

if __name__ == "__main__":
    main()

def find_best_threshold():
    """Run after main() training — sweeps thresholds to find a usable operating point."""
    pass