"""
Precomputes the static JSON data consumed by the public/ dashboard.

Run this after foresight_project_data.csv changes:
    python3 scripts/generate_data.py
"""
import json
import os

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public", "data")


def load_data():
    df = pd.read_csv(os.path.join(ROOT, "foresight_project_data.csv"))
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates()
    df["units_sold"] = df.groupby("sku_id")["units_sold"].transform(lambda x: x.fillna(x.median()))
    df["stock_level"] = df.groupby("sku_id")["stock_level"].transform(lambda x: x.fillna(x.median()))
    df["customer_rating"] = df["customer_rating"].fillna(df["customer_rating"].mean())
    return df


def write_products(df):
    records = df.sort_values(["sku_id", "date"]).copy()
    records["date"] = records["date"].dt.strftime("%Y-%m-%d")
    out_path = os.path.join(OUT_DIR, "products.json")
    with open(out_path, "w") as f:
        json.dump(records.to_dict(orient="records"), f, separators=(",", ":"))
    print(f"wrote {out_path} ({len(records)} rows)")


def write_forecast(df):
    fc_df = df.copy().sort_values(["sku_id", "date"])
    fc_df["month"] = fc_df["date"].dt.month
    fc_df["day_of_week"] = fc_df["date"].dt.dayofweek
    fc_df["is_weekend"] = fc_df["day_of_week"].isin([5, 6]).astype(int)
    fc_df["sales_lag_1"] = fc_df.groupby("sku_id")["units_sold"].shift(1)
    fc_df["sales_lag_7"] = fc_df.groupby("sku_id")["units_sold"].shift(7)
    fc_df["rolling_avg_7"] = fc_df.groupby("sku_id")["units_sold"].transform(lambda x: x.rolling(7, min_periods=1).mean())
    fc_df["rolling_avg_30"] = fc_df.groupby("sku_id")["units_sold"].transform(lambda x: x.rolling(30, min_periods=1).mean())
    fc_df = fc_df.dropna(subset=["sales_lag_1", "sales_lag_7"])

    feature_cols = [
        "month", "day_of_week", "is_weekend", "sales_lag_1", "sales_lag_7",
        "rolling_avg_7", "rolling_avg_30", "on_promotion", "discount_pct",
        "unit_price", "temperature_c",
    ]

    X = fc_df[feature_cols]
    y = fc_df["units_sold"]

    split_date = fc_df["date"].max() - pd.Timedelta(days=60)
    train_mask = fc_df["date"] <= split_date
    test_mask = fc_df["date"] > split_date

    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=True)

    payload = {
        "mae": round(float(mae), 2),
        "r2": round(float(r2), 4),
        "actual": [round(float(v), 2) for v in y_test.values],
        "predicted": [round(float(v), 2) for v in y_pred],
        "feature_importance": {k: round(float(v), 4) for k, v in importances.items()},
        "trained_at": pd.Timestamp.now("UTC").strftime("%Y-%m-%d %H:%M UTC"),
    }

    out_path = os.path.join(OUT_DIR, "forecast.json")
    with open(out_path, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"wrote {out_path} (mae={payload['mae']}, r2={payload['r2']})")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    df = load_data()
    write_products(df)
    write_forecast(df)
