import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Global matplotlib dark theme to match the app
plt.rcParams.update({
    "figure.facecolor": "#140f2d",
    "axes.facecolor": "#140f2d",
    "savefig.facecolor": "#140f2d",
    "axes.edgecolor": "#4c3a6e",
    "axes.labelcolor": "#dce3f5",
    "xtick.color": "#93c5fd",
    "ytick.color": "#93c5fd",
    "text.color": "#dce3f5",
    "grid.color": "#2a2350",
    "axes.grid": True,
    "grid.alpha": 0.4,
    "font.size": 10,
})

NEON_BLUE = "#3b82f6"
NEON_PINK = "#f472b6"
NEON_PURPLE = "#a855f7"
NEON_CYAN = "#22d3ee"
CHART_PALETTE = [NEON_BLUE, NEON_PINK, NEON_PURPLE, NEON_CYAN, "#fb7185", "#60a5fa", "#e879f9", "#38bdf8"]

# Page config
st.set_page_config(page_title="FORESIGHT - Inventory Intelligence", layout="wide")

# Custom CSS - dark blue/pink neon gradient theme
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #060a1f 0%, #0a1128 12%, #142850 28%, #1b2a4a 40%, #2d1b54 55%, #4a1a5e 68%, #6b1e5e 80%, #3a0f4a 92%, #1a0b2e 100%);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a1128 0%, #2d1245 100%);
    border-right: 1px solid rgba(236, 72, 153, 0.35);
}

h1, h2, h3 {
    color: #ffffff !important;
    text-shadow: 0 0 20px rgba(59, 130, 246, 0.6), 0 0 30px rgba(236, 72, 153, 0.4);
}

p, span, label, .stMarkdown {
    color: #dce3f5 !important;
}

[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(59, 130, 246, 0.4);
    border-radius: 14px;
    padding: 16px;
    box-shadow: 0 0 25px rgba(236, 72, 153, 0.2), 0 0 15px rgba(59, 130, 246, 0.2);
}

[data-testid="stMetricValue"] {
    color: #f472b6 !important;
    text-shadow: 0 0 15px rgba(244, 114, 182, 0.7);
}

[data-testid="stMetricLabel"] {
    color: #93c5fd !important;
}

.stDataFrame, [data-testid="stTable"] {
    background: rgba(255, 255, 255, 0.03);
    border-radius: 12px;
    border: 1px solid rgba(59, 130, 246, 0.25);
}

.stButton>button, .stRadio {
    color: #ffffff;
}

[data-testid="stSidebarNav"], .stRadio label {
    color: #dce3f5 !important;
}

.stAlert {
    background: rgba(236, 72, 153, 0.1);
    border: 1px solid rgba(236, 72, 153, 0.4);
    border-radius: 12px;
}

::-webkit-scrollbar {
    width: 10px;
}
::-webkit-scrollbar-track {
    background: #0a1128;
}
::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, #3b82f6, #ec4899);
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

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
    ax.plot(daily_sales.index, daily_sales.values, color=NEON_CYAN, linewidth=1.5)
    ax.fill_between(daily_sales.index, daily_sales.values, color=NEON_CYAN, alpha=0.1)
    ax.set_xlabel("Date")
    ax.set_ylabel("Units Sold")
    st.pyplot(fig)

    # Category comparison
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Units Sold by Category")
        cat_units = filtered_df.groupby('category')['units_sold'].sum().sort_values(ascending=False)
        fig1, ax1 = plt.subplots(figsize=(6, 4))
        ax1.bar(cat_units.index, cat_units.values, color=CHART_PALETTE[:len(cat_units)])
        ax1.set_ylabel("Units Sold")
        plt.setp(ax1.get_xticklabels(), rotation=30, ha='right')
        st.pyplot(fig1)
    with col2:
        st.subheader("Revenue by Category")
        cat_rev = filtered_df.groupby('category')['revenue'].sum().sort_values(ascending=False)
        fig2, ax2 = plt.subplots(figsize=(6, 4))
        ax2.bar(cat_rev.index, cat_rev.values, color=CHART_PALETTE[1:len(cat_rev)+1])
        ax2.set_ylabel("Revenue")
        plt.setp(ax2.get_xticklabels(), rotation=30, ha='right')
        st.pyplot(fig2)

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
    ax.plot(y_test.values, label='Actual', color=NEON_BLUE, linewidth=1.5, alpha=0.9)
    ax.plot(y_pred, label='Predicted', color=NEON_PINK, linewidth=1.5, alpha=0.9)
    ax.legend(facecolor="#140f2d", edgecolor="#4c3a6e", labelcolor="#dce3f5")
    st.pyplot(fig)

    st.subheader("Feature Importance")
    importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=True)
    fig_imp, ax_imp = plt.subplots(figsize=(10, 6))
    ax_imp.barh(importances.index, importances.values, color=CHART_PALETTE[:len(importances)])
    ax_imp.set_xlabel("Importance")
    st.pyplot(fig_imp)

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
    colors = ['#f87171' if x >= 70 else '#fbbf24' if x >= 40 else '#4ade80' for x in risk_sorted['risk_score']]
    ax.barh(risk_sorted['product_name'], risk_sorted['risk_score'], color=colors)
    ax.set_xlabel("Risk Score (0-100)")
    ax.axvline(x=70, color=NEON_PINK, linestyle='--', alpha=0.6)
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
    ax.plot(product_df['date'], product_df['units_sold'], color=NEON_CYAN, linewidth=1.5)
    ax.fill_between(product_df['date'], product_df['units_sold'], color=NEON_CYAN, alpha=0.1)
    ax.set_xlabel("Date")
    ax.set_ylabel("Units Sold")
    st.pyplot(fig)

    st.subheader("Stock Level Over Time")
    fig2, ax2 = plt.subplots(figsize=(12, 4))
    ax2.plot(product_df['date'], product_df['stock_level'], color=NEON_PINK, linewidth=1.5)
    ax2.axhline(y=product_df['reorder_point'].iloc[0], color="#fbbf24", linestyle='--', label='Reorder Point')
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Stock Level")
    ax2.legend(facecolor="#140f2d", edgecolor="#4c3a6e", labelcolor="#dce3f5")
    st.pyplot(fig2)

    st.subheader("Sales by Channel")
    channel_sales = product_df.groupby('sales_channel')['units_sold'].sum().sort_values(ascending=False)
    fig3, ax3 = plt.subplots(figsize=(8, 4))
    ax3.bar(channel_sales.index, channel_sales.values, color=CHART_PALETTE[:len(channel_sales)])
    ax3.set_ylabel("Units Sold")
    st.pyplot(fig3)

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
