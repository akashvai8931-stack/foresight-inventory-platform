import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Page config
st.set_page_config(page_title="FORESIGHT - Inventory Intelligence", layout="wide")

# Load data
@st.cache_data
def load_data():
    df = pd.read_csv('foresight_project_data.csv')
    df['date'] = pd.to_datetime(df['date'])
    df = df.drop_duplicates()
    df['units_sold'] = df.groupby('sku_id')['units_sold'].transform(lambda x: x.fillna(x.median()))
    df['stock_level'] = df.groupby('sku_id')['stock_level'].transform(lambda x: x.fillna(x.median()))
    df['customer_rating'] = df['customer_rating'].fillna(df['customer_rating'].mean())
    return df

df = load_data()

# Sidebar navigation
st.sidebar.title("📦 FORESIGHT")
page = st.sidebar.radio("Navigate", ["Home", "Sales Analytics", "Demand Forecast", "Risk Dashboard", "Product Details", "Executive Summary"])

# Home page
if page == "Home":
    st.title("FORESIGHT: AI-Powered Demand & Inventory Intelligence Platform")
    st.markdown("### Overview")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total SKUs", df['sku_id'].nunique())
    col2.metric("Total Units Sold", f"{int(df['units_sold'].sum()):,}")
    col3.metric("Total Revenue", f"₹{df['revenue'].sum():,.0f}")
    col4.metric("Date Range", f"{df['date'].min().date()} to {df['date'].max().date()}")

    st.markdown("### Sample Data")
    st.dataframe(df.head(20))

# Sales Analytics page
elif page == "Sales Analytics":
    st.title("📊 Sales Analytics")

    # Category filter
    category_filter = st.multiselect("Filter by Category", options=df['category'].unique(), default=df['category'].unique())
    filtered_df = df[df['category'].isin(category_filter)]

    # Daily sales trend
    st.subheader("Daily Sales Trend")
    daily_sales = filtered_df.groupby('date')['units_sold'].sum()
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(daily_sales.index, daily_sales.values)
    ax.set_xlabel("Date")
    ax.set_ylabel("Units Sold")
    st.pyplot(fig)

    # Category comparison
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Units Sold by Category")
        st.bar_chart(filtered_df.groupby('category')['units_sold'].sum())
    with col2:
        st.subheader("Revenue by Category")
        st.bar_chart(filtered_df.groupby('category')['revenue'].sum())

    # Promotion impact
    st.subheader("Promotion Impact")
    promo_avg = filtered_df.groupby('on_promotion')['units_sold'].mean()
    st.write(promo_avg)

# Demand Forecast page
elif page == "Demand Forecast":
    st.title("📈 Demand Forecast")

    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, r2_score

    # Feature engineering (same as notebook)
    fc_df = df.copy()
    fc_df = fc_df.sort_values(['sku_id', 'date'])
    fc_df['month'] = fc_df['date'].dt.month
    fc_df['day_of_week'] = fc_df['date'].dt.dayofweek
    fc_df['is_weekend'] = fc_df['day_of_week'].isin([5, 6]).astype(int)
    fc_df['sales_lag_1'] = fc_df.groupby('sku_id')['units_sold'].shift(1)
    fc_df['sales_lag_7'] = fc_df.groupby('sku_id')['units_sold'].shift(7)
    fc_df['rolling_avg_7'] = fc_df.groupby('sku_id')['units_sold'].transform(lambda x: x.rolling(7, min_periods=1).mean())
    fc_df['rolling_avg_30'] = fc_df.groupby('sku_id')['units_sold'].transform(lambda x: x.rolling(30, min_periods=1).mean())
    fc_df = fc_df.dropna(subset=['sales_lag_1', 'sales_lag_7'])

    feature_cols = ['month', 'day_of_week', 'is_weekend', 'sales_lag_1', 'sales_lag_7',
                     'rolling_avg_7', 'rolling_avg_30', 'on_promotion', 'discount_pct',
                     'unit_price', 'temperature_c']

    X = fc_df[feature_cols]
    y = fc_df['units_sold']

    split_date = fc_df['date'].max() - pd.Timedelta(days=60)
    train_mask = fc_df['date'] <= split_date
    test_mask = fc_df['date'] > split_date

    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    col1, col2 = st.columns(2)
    col1.metric("Model MAE", f"{mae:.2f} units")
    col2.metric("Model R²", f"{r2:.4f}")

    st.subheader("Actual vs Predicted (Test Period)")
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(y_test.values, label='Actual', alpha=0.7)
    ax.plot(y_pred, label='Predicted', alpha=0.7)
    ax.legend()
    st.pyplot(fig)

    st.subheader("Feature Importance")
    importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
    st.bar_chart(importances)

# Risk Dashboard page
elif page == "Risk Dashboard":
    st.title("⚠️ Risk Dashboard")

    # Feature engineering needed for rolling average (forecast proxy)
    risk_df = df.copy()
    risk_df = risk_df.sort_values(['sku_id', 'date'])
    risk_df['rolling_avg_7'] = risk_df.groupby('sku_id')['units_sold'].transform(lambda x: x.rolling(7, min_periods=1).mean())

    # Latest snapshot per SKU
    latest = risk_df.sort_values('date').groupby('sku_id').tail(1).copy()
    latest['forecasted_daily_demand'] = latest['rolling_avg_7']
    latest['days_of_stock_remaining'] = latest['stock_level'] / latest['forecasted_daily_demand']
    latest['stockout_gap_days'] = latest['supplier_lead_time_days'] - latest['days_of_stock_remaining']
    latest['risk_score'] = (latest['stockout_gap_days'] / latest['supplier_lead_time_days'] * 100).clip(lower=0, upper=100).round(1)

    # Summary metrics
    critical_count = (latest['risk_score'] >= 70).sum()
    medium_count = ((latest['risk_score'] >= 40) & (latest['risk_score'] < 70)).sum()
    safe_count = (latest['risk_score'] < 40).sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 Critical Risk", critical_count)
    col2.metric("🟠 Medium Risk", medium_count)
    col3.metric("🟢 Safe", safe_count)

    # Risk score chart
    st.subheader("Risk Score by Product")
    risk_sorted = latest.sort_values('risk_score', ascending=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ['red' if x >= 70 else 'orange' if x >= 40 else 'green' for x in risk_sorted['risk_score']]
    ax.barh(risk_sorted['product_name'], risk_sorted['risk_score'], color=colors)
    ax.set_xlabel("Risk Score (0-100)")
    ax.axvline(x=70, color='black', linestyle='--', alpha=0.3)
    st.pyplot(fig)

    # Detailed table
    st.subheader("Detailed Risk Table")
    st.dataframe(
        latest[['sku_id', 'product_name', 'stock_level', 'forecasted_daily_demand',
                'days_of_stock_remaining', 'supplier_lead_time_days', 'risk_score']]
        .sort_values('risk_score', ascending=False)
        .reset_index(drop=True)
    )

# Product Details page
elif page == "Product Details":
    st.title("🔍 Product Details")

    selected_sku = st.selectbox("Select a Product", options=sorted(df['sku_id'].unique()))
    product_df = df[df['sku_id'] == selected_sku].sort_values('date')
    product_name = product_df['product_name'].iloc[0]

    st.subheader(f"{product_name} ({selected_sku})")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Category", product_df['category'].iloc[0])
    col2.metric("Vendor", product_df['vendor'].iloc[0])
    col3.metric("Unit Price", f"₹{product_df['unit_price'].iloc[0]:.2f}")
    col4.metric("Total Units Sold (YTD)", f"{int(product_df['units_sold'].sum()):,}")

    col5, col6, col7 = st.columns(3)
    col5.metric("Current Stock", f"{int(product_df['stock_level'].iloc[-1])}")
    col6.metric("Reorder Point", f"{int(product_df['reorder_point'].iloc[0])}")
    col7.metric("Supplier Lead Time", f"{int(product_df['supplier_lead_time_days'].iloc[0])} days")

    st.subheader("Sales History")
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(product_df['date'], product_df['units_sold'])
    ax.set_xlabel("Date")
    ax.set_ylabel("Units Sold")
    st.pyplot(fig)

    st.subheader("Stock Level Over Time")
    fig2, ax2 = plt.subplots(figsize=(12, 4))
    ax2.plot(product_df['date'], product_df['stock_level'], color='orange')
    ax2.axhline(y=product_df['reorder_point'].iloc[0], color='red', linestyle='--', label='Reorder Point')
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Stock Level")
    ax2.legend()
    st.pyplot(fig2)

    st.subheader("Sales by Channel")
    st.bar_chart(product_df.groupby('sales_channel')['units_sold'].sum())

# Executive Summary page
elif page == "Executive Summary":
    st.title("📋 Executive Summary")
    st.markdown("### FORESIGHT — AI-Powered Demand & Inventory Intelligence Platform")

    # Recompute risk for summary
    exec_df = df.copy().sort_values(['sku_id', 'date'])
    exec_df['rolling_avg_7'] = exec_df.groupby('sku_id')['units_sold'].transform(lambda x: x.rolling(7, min_periods=1).mean())
    latest_exec = exec_df.sort_values('date').groupby('sku_id').tail(1).copy()
    latest_exec['days_of_stock_remaining'] = latest_exec['stock_level'] / latest_exec['rolling_avg_7']
    latest_exec['stockout_gap_days'] = latest_exec['supplier_lead_time_days'] - latest_exec['days_of_stock_remaining']
    latest_exec['risk_score'] = (latest_exec['stockout_gap_days'] / latest_exec['supplier_lead_time_days'] * 100).clip(lower=0, upper=100).round(1)

    critical_skus = latest_exec[latest_exec['risk_score'] >= 70].sort_values('risk_score', ascending=False)

    st.markdown("#### Key Business Metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Revenue (YTD)", f"₹{df['revenue'].sum():,.0f}")
    col2.metric("Total Units Sold", f"{int(df['units_sold'].sum()):,}")
    col3.metric("Top Category", df.groupby('category')['revenue'].sum().idxmax())
    col4.metric("SKUs at Critical Risk", f"{len(critical_skus)} / {df['sku_id'].nunique()}")

    st.markdown("#### Top Findings")
    st.markdown(f"""
    - **Seasonality:** Sales rise sharply in November–December (holiday demand), with the lowest demand in January–February.
    - **Category performance:** **{df.groupby('category')['revenue'].sum().idxmax()}** leads in both units sold and revenue.
    - **Promotions:** Products on promotion sell **{(df[df['on_promotion']==True]['units_sold'].mean() / df[df['on_promotion']==False]['units_sold'].mean() - 1) * 100:.0f}% more** on average than non-promoted items.
    - **Inventory risk:** **{len(critical_skus)} of {df['sku_id'].nunique()} SKUs** are projected to stock out before their next supplier delivery arrives.
    """)

    st.markdown("#### Products Requiring Immediate Action")
    st.dataframe(
        critical_skus[['sku_id', 'product_name', 'risk_score', 'stock_level', 'supplier_lead_time_days']]
        .reset_index(drop=True)
    )

    st.markdown("#### Recommendation")
    st.info("Prioritize reordering for the SKUs listed above. Consider renegotiating supplier lead times for chronically high-risk products, or increasing their reorder points to build a larger safety buffer.")