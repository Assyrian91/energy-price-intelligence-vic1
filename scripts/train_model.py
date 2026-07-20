"""
Train an XGBoost classifier to predict electricity price spikes (RRP > $300/MWh)
using the energy_features view from Supabase.

Setup:
  python -m pip install psycopg2-binary python-dotenv pandas xgboost scikit-learn --break-system-packages

Uses the same .env file as load_to_supabase.py (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD).
"""
import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from sklearn.metrics import classification_report, roc_auc_score
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

    # First row has no lag value (nothing before it) — drop it
    df = df.dropna(subset=["rrp_prev_interval"])

    print(f"Total rows: {len(df):,}")
    print(f"Date range: {df['settlement_date'].min()} to {df['settlement_date'].max()}")

    # --- Chronological split: train on the past, test on the future ---
    split_date = "2026-05-01"
    train = df[df["settlement_date"] < split_date]
    test = df[df["settlement_date"] >= split_date]
    print(f"\nTrain: {len(train):,} rows ({train['settlement_date'].min()} to {train['settlement_date'].max()})")
    print(f"Test:  {len(test):,} rows ({test['settlement_date'].min()} to {test['settlement_date'].max()})")
    print(f"Train spike rate: {train['is_spike'].mean():.2%}")
    print(f"Test spike rate:  {test['is_spike'].mean():.2%}")

    # --- Features: encode categoricals, drop leakage-prone columns ---
    feature_cols = [
        "total_demand", "hour_of_day", "month_num", "is_peak_hour",
        "rrp_prev_interval", "rrp_rolling_1hr", "is_known_outage_period"
    ]
    cat_cols = ["day_type", "season"]

    train_X = pd.get_dummies(train[feature_cols + cat_cols], columns=cat_cols)
    test_X = pd.get_dummies(test[feature_cols + cat_cols], columns=cat_cols)
    # align columns in case a category is missing in test
    test_X = test_X.reindex(columns=train_X.columns, fill_value=0)

    train_y = train["is_spike"]
    test_y = test["is_spike"]

    # --- Train ---
    print("\nTraining XGBoost classifier...")
    model = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        scale_pos_weight=(train_y == 0).sum() / (train_y == 1).sum(),  # handle class imbalance
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(train_X, train_y)

    # --- Evaluate on unseen future data ---
    pred = model.predict(test_X)
    pred_proba = model.predict_proba(test_X)[:, 1]

    print("\n--- Classification report (test set, unseen future data) ---")
    print(classification_report(test_y, pred, digits=3))
    print(f"ROC-AUC: {roc_auc_score(test_y, pred_proba):.4f}")

    print("\n--- Confusion matrix ---")
    from sklearn.metrics import confusion_matrix
    cm = confusion_matrix(test_y, pred)
    print(f"                 Predicted No-Spike   Predicted Spike")
    print(f"Actual No-Spike        {cm[0][0]:>6}              {cm[0][1]:>6}")
    print(f"Actual Spike           {cm[1][0]:>6}              {cm[1][1]:>6}")
    print(f"\nMissed spikes (false negatives): {cm[1][0]}")
    print(f"False alarms (false positives):  {cm[0][1]}")

    # Show the actual missed spikes with their timestamps and prices
    test_with_preds = test.copy()
    test_with_preds["predicted"] = pred
    missed = test_with_preds[(test_with_preds["is_spike"] == 1) & (test_with_preds["predicted"] == 0)]
    if len(missed) > 0:
        print("\n--- Missed spikes (model said no, but it was a real spike) ---")
        print(missed[["settlement_date", "rrp", "rrp_prev_interval", "total_demand"]].to_string(index=False))

    print("\n--- Feature importance ---")
    importances = pd.Series(model.feature_importances_, index=train_X.columns).sort_values(ascending=False)
    print(importances.to_string())

    model.save_model("spike_model.json")
    print("\nModel saved to spike_model.json")

if __name__ == "__main__":
    main()