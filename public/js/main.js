const PALETTE = ["#3b82f6", "#f472b6", "#a855f7", "#22d3ee", "#fb7185", "#60a5fa", "#e879f9", "#38bdf8"];
const TEXT_COLOR = "#dce3f5";
const TICK_COLOR = "#93c5fd";
const GRID_COLOR = "rgba(147, 197, 253, 0.12)";

Chart.defaults.color = TEXT_COLOR;
Chart.defaults.borderColor = GRID_COLOR;
Chart.defaults.font.family = "'Segoe UI', Roboto, sans-serif";

const state = {
  rows: [],
  forecast: null,
  categories: [],
  warehouses: [],
  filters: {
    salesCategories: new Set(),
    invWarehouses: new Set(),
    invCategories: new Set(),
  },
  selectedSku: null,
  charts: {},
};

// ---------- helpers ----------
function fmtInt(n) {
  return Math.round(n).toLocaleString("en-US");
}
function fmtCurrency(n) {
  return "₹" + fmtInt(n);
}
function unique(rows, key) {
  return [...new Set(rows.map((r) => r[key]))].sort();
}
function sum(rows, key) {
  return rows.reduce((acc, r) => acc + (r[key] || 0), 0);
}
function mean(rows, key) {
  return rows.length ? sum(rows, key) / rows.length : 0;
}
function groupBy(rows, key) {
  const map = new Map();
  for (const r of rows) {
    const k = r[key];
    if (!map.has(k)) map.set(k, []);
    map.get(k).push(r);
  }
  return map;
}
function destroyChart(id) {
  if (state.charts[id]) {
    state.charts[id].destroy();
    delete state.charts[id];
  }
}
function makeChart(id, config) {
  destroyChart(id);
  const ctx = document.getElementById(id);
  state.charts[id] = new Chart(ctx, config);
  return state.charts[id];
}
function darkGridOptions(extra = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: TEXT_COLOR } },
      tooltip: { titleColor: "#fff", bodyColor: TEXT_COLOR, backgroundColor: "#140f2d", borderColor: "#4c3a6e", borderWidth: 1 },
    },
    scales: {
      x: { ticks: { color: TICK_COLOR }, grid: { color: GRID_COLOR } },
      y: { ticks: { color: TICK_COLOR }, grid: { color: GRID_COLOR } },
    },
    ...extra,
  };
}
function renderTable(container, columns, rows) {
  if (!rows.length) {
    container.innerHTML = '<p class="caption">No data for the current filters.</p>';
    return;
  }
  const thead = `<thead><tr>${columns.map((c) => `<th>${c.label}</th>`).join("")}</tr></thead>`;
  const tbody = `<tbody>${rows
    .map(
      (r) =>
        `<tr>${columns.map((c) => `<td>${c.fmt ? c.fmt(r[c.key], r) : r[c.key]}</td>`).join("")}</tr>`
    )
    .join("")}</tbody>`;
  container.innerHTML = `<table>${thead}${tbody}</table>`;
}
function metricCard(label, value) {
  return `<div class="metric"><div class="metric-label">${label}</div><div class="metric-value">${value}</div></div>`;
}
function chipGroup(container, options, selectedSet, onChange) {
  container.innerHTML = "";
  options.forEach((opt) => {
    const btn = document.createElement("button");
    btn.className = "chip" + (selectedSet.has(opt) ? " active" : "");
    btn.textContent = opt;
    btn.onclick = () => {
      if (selectedSet.has(opt)) selectedSet.delete(opt);
      else selectedSet.add(opt);
      btn.classList.toggle("active");
      onChange();
    };
    container.appendChild(btn);
  });
}

// rolling 7-day average per sku (row-based, matches pandas .rolling(7, min_periods=1) on daily data)
function attachRollingAvg7(rows) {
  const bySku = groupBy(rows, "sku_id");
  for (const group of bySku.values()) {
    group.sort((a, b) => (a.date < b.date ? -1 : 1));
    let windowVals = [];
    for (const row of group) {
      windowVals.push(row.units_sold);
      if (windowVals.length > 7) windowVals.shift();
      row.rollingAvg7 = windowVals.reduce((a, b) => a + b, 0) / windowVals.length;
    }
  }
}

function latestPerSku(rows) {
  const sorted = [...rows].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  const latest = new Map();
  for (const r of sorted) latest.set(r.sku_id, r);
  return [...latest.values()];
}

function computeRiskTable(rows) {
  const latest = latestPerSku(rows);
  return latest.map((r) => {
    const forecasted = r.rollingAvg7;
    const daysRemaining = forecasted > 0 ? r.stock_level / forecasted : Infinity;
    const gap = r.supplier_lead_time_days - daysRemaining;
    let riskScore = (gap / r.supplier_lead_time_days) * 100;
    riskScore = Math.max(0, Math.min(100, riskScore));
    return {
      ...r,
      forecasted_daily_demand: forecasted,
      days_of_stock_remaining: daysRemaining,
      stockout_gap_days: gap,
      risk_score: Math.round(riskScore * 10) / 10,
    };
  });
}

// ---------- page renderers ----------
function renderHome() {
  const rows = state.rows;
  document.getElementById("home-metrics").innerHTML = [
    metricCard("Total SKUs", unique(rows, "sku_id").length),
    metricCard("Total Units Sold", fmtInt(sum(rows, "units_sold"))),
    metricCard("Total Revenue", fmtCurrency(sum(rows, "revenue"))),
    metricCard("Date Range", `${rows[0].date} to ${rows[rows.length - 1].date}`),
  ].join("");

  const cols = [
    { key: "date", label: "date" },
    { key: "sku_id", label: "sku_id" },
    { key: "product_name", label: "product_name" },
    { key: "category", label: "category" },
    { key: "warehouse_location", label: "warehouse_location" },
    { key: "sales_channel", label: "sales_channel" },
    { key: "units_sold", label: "units_sold" },
    { key: "stock_level", label: "stock_level" },
    { key: "revenue", label: "revenue", fmt: (v) => v.toFixed(2) },
  ];
  renderTable(document.getElementById("home-sample"), cols, rows.slice(0, 20));
}

function renderSales() {
  if (state.filters.salesCategories.size === 0) {
    state.categories.forEach((c) => state.filters.salesCategories.add(c));
  }
  chipGroup(document.getElementById("sales-category-filter"), state.categories, state.filters.salesCategories, drawSalesCharts);
  drawSalesCharts();
}

function drawSalesCharts() {
  const filtered = state.rows.filter((r) => state.filters.salesCategories.has(r.category));

  const byDate = groupBy(filtered, "date");
  const dates = [...byDate.keys()].sort();
  const dailyUnits = dates.map((d) => sum(byDate.get(d), "units_sold"));

  makeChart("chart-daily-sales", {
    type: "line",
    data: {
      labels: dates,
      datasets: [
        {
          label: "Units Sold",
          data: dailyUnits,
          borderColor: "#22d3ee",
          backgroundColor: "rgba(34, 211, 238, 0.1)",
          fill: true,
          pointRadius: 0,
          borderWidth: 1.5,
        },
      ],
    },
    options: darkGridOptions({ plugins: { legend: { display: false } } }),
  });

  const byCat = groupBy(filtered, "category");
  const catUnits = [...byCat.entries()].map(([cat, rs]) => [cat, sum(rs, "units_sold")]).sort((a, b) => b[1] - a[1]);
  makeChart("chart-units-category", {
    type: "bar",
    data: {
      labels: catUnits.map((c) => c[0]),
      datasets: [{ label: "Units Sold", data: catUnits.map((c) => c[1]), backgroundColor: PALETTE }],
    },
    options: darkGridOptions({ plugins: { legend: { display: false } } }),
  });

  const catRev = [...byCat.entries()].map(([cat, rs]) => [cat, sum(rs, "revenue")]).sort((a, b) => b[1] - a[1]);
  makeChart("chart-revenue-category", {
    type: "bar",
    data: {
      labels: catRev.map((c) => c[0]),
      datasets: [{ label: "Revenue", data: catRev.map((c) => c[1]), backgroundColor: PALETTE.slice(1) }],
    },
    options: darkGridOptions({ plugins: { legend: { display: false } } }),
  });

  const byPromo = groupBy(filtered, "on_promotion");
  const promoRows = [...byPromo.entries()].map(([k, rs]) => ({ on_promotion: k ? "True" : "False", units_sold: mean(rs, "units_sold").toFixed(2) }));
  renderTable(document.getElementById("sales-promo"), [
    { key: "on_promotion", label: "on_promotion" },
    { key: "units_sold", label: "mean units_sold" },
  ], promoRows);
}

function renderForecast() {
  const f = state.forecast;
  document.getElementById("forecast-caption").textContent = `Model snapshot trained ${f.trained_at} on a 60-day holdout. Regenerate via scripts/generate_data.py after the dataset changes.`;
  document.getElementById("forecast-metrics").innerHTML = [
    metricCard("Model MAE", `${f.mae.toFixed(2)} units`),
    metricCard("Model R²", f.r2.toFixed(4)),
  ].join("");

  makeChart("chart-forecast-line", {
    type: "line",
    data: {
      labels: f.actual.map((_, i) => i),
      datasets: [
        { label: "Actual", data: f.actual, borderColor: "#3b82f6", pointRadius: 0, borderWidth: 1.5 },
        { label: "Predicted", data: f.predicted, borderColor: "#f472b6", pointRadius: 0, borderWidth: 1.5 },
      ],
    },
    options: darkGridOptions(),
  });

  const entries = Object.entries(f.feature_importance).sort((a, b) => b[1] - a[1]);
  makeChart("chart-forecast-importance", {
    type: "bar",
    data: {
      labels: entries.map((e) => e[0]),
      datasets: [{ label: "Importance", data: entries.map((e) => e[1]), backgroundColor: PALETTE }],
    },
    options: darkGridOptions({ indexAxis: "y", plugins: { legend: { display: false } } }),
  });
}

function renderInventory() {
  if (state.filters.invWarehouses.size === 0) state.warehouses.forEach((w) => state.filters.invWarehouses.add(w));
  if (state.filters.invCategories.size === 0) state.categories.forEach((c) => state.filters.invCategories.add(c));
  chipGroup(document.getElementById("inv-warehouse-filter"), state.warehouses, state.filters.invWarehouses, drawInventory);
  chipGroup(document.getElementById("inv-category-filter"), state.categories, state.filters.invCategories, drawInventory);
  drawInventory();
}

function drawInventory() {
  const filtered = state.rows.filter(
    (r) => state.filters.invWarehouses.has(r.warehouse_location) && state.filters.invCategories.has(r.category)
  );
  const latest = latestPerSku(filtered).map((r) => {
    const status = r.stock_level < r.reorder_point ? "Understocked" : r.stock_level > r.reorder_point * 3 ? "Overstocked" : "Adequate";
    return { ...r, stock_status: status, inventory_value: r.stock_level * r.unit_cost };
  });

  document.getElementById("inv-metrics").innerHTML = [
    metricCard("Total Units in Stock", fmtInt(sum(latest, "stock_level"))),
    metricCard("Total Inventory Value", fmtCurrency(sum(latest, "inventory_value"))),
    metricCard("Understocked SKUs", latest.filter((r) => r.stock_status === "Understocked").length),
    metricCard("Overstocked SKUs", latest.filter((r) => r.stock_status === "Overstocked").length),
  ].join("");

  const sorted = [...latest].sort((a, b) => a.stock_level - b.stock_level);
  makeChart("chart-stock-reorder", {
    type: "bar",
    data: {
      labels: sorted.map((r) => r.product_name),
      datasets: [
        { type: "bar", label: "Current Stock", data: sorted.map((r) => r.stock_level), backgroundColor: "rgba(59,130,246,0.8)" },
        {
          type: "line",
          label: "Reorder Point",
          data: sorted.map((r) => r.reorder_point),
          showLine: false,
          pointStyle: "circle",
          pointRadius: 6,
          pointBackgroundColor: "#f472b6",
          pointBorderColor: "#f472b6",
        },
      ],
    },
    options: darkGridOptions({ indexAxis: "y" }),
  });

  const byWh = groupBy(latest, "warehouse_location");
  const statuses = ["Understocked", "Adequate", "Overstocked"];
  const whLabels = [...byWh.keys()].sort();
  makeChart("chart-stock-status", {
    type: "bar",
    data: {
      labels: whLabels,
      datasets: statuses.map((status, i) => ({
        label: status,
        data: whLabels.map((wh) => byWh.get(wh).filter((r) => r.stock_status === status).length),
        backgroundColor: PALETTE[i],
      })),
    },
    options: darkGridOptions({ scales: { x: { stacked: true, ticks: { color: TICK_COLOR }, grid: { color: GRID_COLOR } }, y: { stacked: true, ticks: { color: TICK_COLOR }, grid: { color: GRID_COLOR } } } }),
  });

  const tableRows = [...latest].sort((a, b) => b.inventory_value - a.inventory_value);
  renderTable(document.getElementById("inv-table"), [
    { key: "sku_id", label: "sku_id" },
    { key: "product_name", label: "product_name" },
    { key: "warehouse_location", label: "warehouse_location" },
    { key: "stock_level", label: "stock_level" },
    { key: "reorder_point", label: "reorder_point" },
    { key: "stock_status", label: "stock_status" },
    { key: "unit_cost", label: "unit_cost", fmt: (v) => v.toFixed(2) },
    { key: "inventory_value", label: "inventory_value", fmt: (v) => fmtInt(v) },
  ], tableRows);
}

function renderRisk() {
  const risk = computeRiskTable(state.rows);
  const critical = risk.filter((r) => r.risk_score >= 70).length;
  const medium = risk.filter((r) => r.risk_score >= 40 && r.risk_score < 70).length;
  const safe = risk.filter((r) => r.risk_score < 40).length;

  document.getElementById("risk-metrics").innerHTML = [
    metricCard("🔴 Critical Risk", critical),
    metricCard("🟠 Medium Risk", medium),
    metricCard("🟢 Safe", safe),
  ].join("");

  const sorted = [...risk].sort((a, b) => b.risk_score - a.risk_score);
  const colors = sorted.map((r) => (r.risk_score >= 70 ? "#f87171" : r.risk_score >= 40 ? "#fbbf24" : "#4ade80"));
  makeChart("chart-risk", {
    type: "bar",
    data: { labels: sorted.map((r) => r.product_name), datasets: [{ label: "Risk Score", data: sorted.map((r) => r.risk_score), backgroundColor: colors }] },
    options: darkGridOptions({ indexAxis: "y", plugins: { legend: { display: false } } }),
  });

  renderTable(document.getElementById("risk-table"), [
    { key: "sku_id", label: "sku_id" },
    { key: "product_name", label: "product_name" },
    { key: "stock_level", label: "stock_level" },
    { key: "forecasted_daily_demand", label: "forecasted_daily_demand", fmt: (v) => v.toFixed(2) },
    { key: "days_of_stock_remaining", label: "days_of_stock_remaining", fmt: (v) => (isFinite(v) ? v.toFixed(1) : "∞") },
    { key: "supplier_lead_time_days", label: "supplier_lead_time_days" },
    { key: "risk_score", label: "risk_score" },
  ], sorted);
}

function renderProductPage() {
  const skus = unique(state.rows, "sku_id");
  const select = document.getElementById("product-select");
  select.innerHTML = skus.map((s) => `<option value="${s}">${s}</option>`).join("");
  if (!state.selectedSku || !skus.includes(state.selectedSku)) state.selectedSku = skus[0];
  select.value = state.selectedSku;
  select.onchange = () => {
    state.selectedSku = select.value;
    drawProduct();
  };
  drawProduct();
}

function drawProduct() {
  const productRows = state.rows.filter((r) => r.sku_id === state.selectedSku).sort((a, b) => (a.date < b.date ? -1 : 1));
  const first = productRows[0];
  const last = productRows[productRows.length - 1];

  document.getElementById("product-title").textContent = `${first.product_name} (${state.selectedSku})`;
  document.getElementById("product-metrics-1").innerHTML = [
    metricCard("Category", first.category),
    metricCard("Vendor", first.vendor),
    metricCard("Unit Price", `₹${first.unit_price.toFixed(2)}`),
    metricCard("Total Units Sold (YTD)", fmtInt(sum(productRows, "units_sold"))),
  ].join("");
  document.getElementById("product-metrics-2").innerHTML = [
    metricCard("Current Stock", fmtInt(last.stock_level)),
    metricCard("Reorder Point", fmtInt(first.reorder_point)),
    metricCard("Supplier Lead Time", `${first.supplier_lead_time_days} days`),
  ].join("");

  makeChart("chart-product-sales", {
    type: "line",
    data: { labels: productRows.map((r) => r.date), datasets: [{ label: "Units Sold", data: productRows.map((r) => r.units_sold), borderColor: "#22d3ee", backgroundColor: "rgba(34,211,238,0.1)", fill: true, pointRadius: 0, borderWidth: 1.5 }] },
    options: darkGridOptions({ plugins: { legend: { display: false } } }),
  });

  makeChart("chart-product-stock", {
    type: "line",
    data: {
      labels: productRows.map((r) => r.date),
      datasets: [
        { label: "Stock Level", data: productRows.map((r) => r.stock_level), borderColor: "#f472b6", pointRadius: 0, borderWidth: 1.5 },
        { label: "Reorder Point", data: productRows.map(() => first.reorder_point), borderColor: "#fbbf24", borderDash: [6, 4], pointRadius: 0, borderWidth: 1.5 },
      ],
    },
    options: darkGridOptions(),
  });

  const byChannel = groupBy(productRows, "sales_channel");
  const channelData = [...byChannel.entries()].map(([ch, rs]) => [ch, sum(rs, "units_sold")]).sort((a, b) => b[1] - a[1]);
  makeChart("chart-product-channel", {
    type: "bar",
    data: { labels: channelData.map((c) => c[0]), datasets: [{ label: "Units Sold", data: channelData.map((c) => c[1]), backgroundColor: PALETTE }] },
    options: darkGridOptions({ plugins: { legend: { display: false } } }),
  });
}

function renderSummary() {
  const rows = state.rows;
  const risk = computeRiskTable(rows);
  const critical = risk.filter((r) => r.risk_score >= 70).sort((a, b) => b.risk_score - a.risk_score);
  const byCat = groupBy(rows, "category");
  const topCategory = [...byCat.entries()].map(([cat, rs]) => [cat, sum(rs, "revenue")]).sort((a, b) => b[1] - a[1])[0][0];

  const promoTrue = rows.filter((r) => r.on_promotion === true);
  const promoFalse = rows.filter((r) => r.on_promotion === false);
  const promoLift = ((mean(promoTrue, "units_sold") / mean(promoFalse, "units_sold") - 1) * 100).toFixed(0);

  document.getElementById("summary-metrics").innerHTML = [
    metricCard("Total Revenue (YTD)", fmtCurrency(sum(rows, "revenue"))),
    metricCard("Total Units Sold", fmtInt(sum(rows, "units_sold"))),
    metricCard("Top Category", topCategory),
    metricCard("SKUs at Critical Risk", `${critical.length} / ${unique(rows, "sku_id").length}`),
  ].join("");

  document.getElementById("summary-findings").innerHTML = [
    `<li><strong>Seasonality:</strong> Sales rise sharply in November–December (holiday demand), with the lowest demand in January–February.</li>`,
    `<li><strong>Category performance:</strong> <strong>${topCategory}</strong> leads in both units sold and revenue.</li>`,
    `<li><strong>Promotions:</strong> Products on promotion sell <strong>${promoLift}% more</strong> on average than non-promoted items.</li>`,
    `<li><strong>Inventory risk:</strong> <strong>${critical.length} of ${unique(rows, "sku_id").length} SKUs</strong> are projected to stock out before their next supplier delivery arrives.</li>`,
  ].join("");

  renderTable(document.getElementById("summary-table"), [
    { key: "sku_id", label: "sku_id" },
    { key: "product_name", label: "product_name" },
    { key: "risk_score", label: "risk_score" },
    { key: "stock_level", label: "stock_level" },
    { key: "supplier_lead_time_days", label: "supplier_lead_time_days" },
  ], critical);
}

// ---------- routing ----------
const RENDERERS = {
  home: renderHome,
  sales: renderSales,
  forecast: renderForecast,
  inventory: renderInventory,
  risk: renderRisk,
  product: renderProductPage,
  summary: renderSummary,
};

function showPage(page) {
  if (!RENDERERS[page]) page = "home";
  document.querySelectorAll(".nav-item").forEach((btn) => btn.classList.toggle("active", btn.dataset.page === page));
  const content = document.getElementById("content");
  const tpl = document.getElementById(`tpl-${page}`);
  content.innerHTML = "";
  content.appendChild(tpl.content.cloneNode(true));
  RENDERERS[page]();
  location.hash = page;
}

function init() {
  document.getElementById("nav").addEventListener("click", (e) => {
    const btn = e.target.closest(".nav-item");
    if (btn) showPage(btn.dataset.page);
  });

  Promise.all([fetch("data/products.json").then((r) => r.json()), fetch("data/forecast.json").then((r) => r.json())])
    .then(([products, forecast]) => {
      state.rows = products;
      state.forecast = forecast;
      attachRollingAvg7(state.rows);
      state.categories = unique(state.rows, "category");
      state.warehouses = unique(state.rows, "warehouse_location");
      const initialPage = (location.hash || "#home").slice(1);
      showPage(RENDERERS[initialPage] ? initialPage : "home");
    })
    .catch((err) => {
      document.getElementById("content").innerHTML = `<p class="caption">Failed to load dashboard data: ${err.message}</p>`;
    });
}

init();
