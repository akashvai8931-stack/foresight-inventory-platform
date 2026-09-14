from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

app = FastAPI(title="FORESIGHT Demand Forecast API")

# ----- Load data and train model once at startup -----
df = pd.read_csv('foresight_project_data.csv')
df['date'] = pd.to_datetime(df['date'])
df = df.drop_duplicates()
df['units_sold'] = df.groupby('sku_id')['units_sold'].transform(lambda x: x.fillna(x.median()))
df['stock_level'] = df.groupby('sku_id')['stock_level'].transform(lambda x: x.fillna(x.median()))
df['customer_rating'] = df['customer_rating'].fillna(df['customer_rating'].mean())

df = df.sort_values(['sku_id', 'date'])
df['month'] = df['date'].dt.month
df['day_of_week'] = df['date'].dt.dayofweek
df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
df['sales_lag_1'] = df.groupby('sku_id')['units_sold'].shift(1)
df['sales_lag_7'] = df.groupby('sku_id')['units_sold'].shift(7)
df['rolling_avg_7'] = df.groupby('sku_id')['units_sold'].transform(lambda x: x.rolling(7, min_periods=1).mean())
df['rolling_avg_30'] = df.groupby('sku_id')['units_sold'].transform(lambda x: x.rolling(30, min_periods=1).mean())
df_model = df.dropna(subset=['sales_lag_1', 'sales_lag_7'])

feature_cols = ['month', 'day_of_week', 'is_weekend', 'sales_lag_1', 'sales_lag_7',
                 'rolling_avg_7', 'rolling_avg_30', 'on_promotion', 'discount_pct',
                 'unit_price', 'temperature_c']

X = df_model[feature_cols]
y = df_model['units_sold']

model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X, y)

# ----- Request schema -----
class ForecastRequest(BaseModel):
    month: int
    day_of_week: int
    is_weekend: int
    sales_lag_1: float
    sales_lag_7: float
    rolling_avg_7: float
    rolling_avg_30: float
    on_promotion: bool
    discount_pct: float
    unit_price: float
    temperature_c: float


@app.get("/")
def home():
    return {"message": "FORESIGHT Demand Forecast API is running. POST to /predict for a forecast."}


@app.post("/predict")
def predict(request: ForecastRequest):
    input_df = pd.DataFrame([request.dict()])[feature_cols]
    prediction = model.predict(input_df)[0]
    return {"predicted_units_sold": round(float(prediction), 2)}


@app.get("/skus")
def list_skus():
    return {"skus": sorted(df['sku_id'].unique().tolist())}


@app.get("/sku/{sku_id}/latest")
def latest_sku_snapshot(sku_id: str):
    sku_df = df[df['sku_id'] == sku_id].sort_values('date')
    if sku_df.empty:
        return {"error": f"SKU {sku_id} not found"}
    latest = sku_df.iloc[-1]
    return {
        "sku_id": sku_id,
        "product_name": latest['product_name'],
        "stock_level": float(latest['stock_level']),
        "rolling_avg_7": float(latest['rolling_avg_7']),
        "supplier_lead_time_days": int(latest['supplier_lead_time_days'])
    }