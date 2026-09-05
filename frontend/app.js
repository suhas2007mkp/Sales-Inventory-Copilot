/**
 * Sales & Inventory Copilot (PS03)
 * Frontend Application Logic & Chart.js Visualizations
 */

// Global State
let currentStoreId = "";
let chartInstances = {};
let allAlertsData = [];
let allInventoryData = [];

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  initStoreSelector();
  loadDashboardData();
  loadAlertsData();
  loadInventoryData();
  loadConfigData();
});

// Switch Active Tab
function switchTab(tabId, filterParam = null) {
  // Update sidebar buttons
  document.querySelectorAll(".nav-item").forEach(btn => btn.classList.remove("active"));
  const activeBtn = document.getElementById(`nav-${tabId}`);
  if (activeBtn) activeBtn.classList.add("active");

  // Update panes
  document.querySelectorAll(".tab-pane").forEach(pane => pane.classList.remove("active"));
  const activePane = document.getElementById(`pane-${tabId}`);
  if (activePane) activePane.classList.add("active");

  // If jumping to alerts with specific filter
  if (tabId === "alerts" && filterParam) {
    const filterSelect = document.getElementById("alert-filter-type");
    if (filterSelect) {
      filterSelect.value = filterParam;
      filterAlerts();
    }
  }

  // Update page title
  const titleEl = document.getElementById("page-title");
  const subEl = document.getElementById("page-subtitle");
  if (tabId === "dashboard") {
    titleEl.textContent = "Store Manager Dashboard";
    subEl.textContent = "Real-time inventory velocity, stock-out forecasts & grounded recommendations";
  } else if (tabId === "copilot") {
    titleEl.textContent = "AI Retail Copilot";
    subEl.textContent = "Deterministic business calculations with grounded GenAI reasoning";
  } else if (tabId === "alerts") {
    titleEl.textContent = "Attention Required Alerts";
    subEl.textContent = "Likely stockouts, overstock, and sales anomalies with action recommendations";
  } else if (tabId === "inventory") {
    titleEl.textContent = "Inventory Matrix & Catalogue";
    subEl.textContent = "Store catalogue with run-rates, days of supply, and stock health";
  }
}

// Store Selector
async function initStoreSelector() {
  try {
    const res = await fetch("/api/stores");
    const stores = await res.json();
    const select = document.getElementById("store-select");
    select.innerHTML = '<option value="">All Stores (Consolidated)</option>';
    stores.forEach(s => {
      const opt = document.createElement("option");
      opt.value = s.store_id;
      opt.textContent = `${s.store_name} (${s.location.split(",")[0]})`;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error("Error loading stores:", err);
  }
}

function onStoreChange() {
  const select = document.getElementById("store-select");
  currentStoreId = select.value;
  loadDashboardData();
  loadAlertsData();
  loadInventoryData();
}

// -------------------------------------------------------------
// DASHBOARD DATA & CHARTS
// -------------------------------------------------------------
async function loadDashboardData() {
  const queryParam = currentStoreId ? `?store_id=${currentStoreId}` : "";
  try {
    // 1. Load KPI Summary
    const summaryRes = await fetch(`/api/dashboard${queryParam}`);
    const summary = await summaryRes.json();

    document.getElementById("kpi-today-revenue").textContent = `₹${summary.today_sales_revenue.toLocaleString('en-IN')}`;
    document.getElementById("kpi-today-units").textContent = `${summary.today_units_sold} units sold (${summary.latest_date})`;
    document.getElementById("kpi-low-stock").textContent = summary.low_stock_count;
    document.getElementById("kpi-overstock").textContent = summary.overstock_count;
    document.getElementById("kpi-slow-moving").textContent = summary.slow_moving_count;
    document.getElementById("sidebar-alert-count").textContent = summary.active_alerts_count;

    // 2. Load Charts
    loadSalesTrendChart(queryParam);
    loadTopProductsChart(queryParam);
    loadStockLevelsChart(queryParam);
    loadCategoryChart(queryParam);
  } catch (err) {
    console.error("Error loading dashboard KPIs:", err);
  }
}

// Chart 1: Sales Trend Line Chart
async function loadSalesTrendChart(queryParam) {
  try {
    const res = await fetch(`/api/sales/trends${queryParam}`);
    const data = await res.json();

    const labels = data.map(d => d.date.slice(5)); // 'MM-DD'
    const revenues = data.map(d => d.total_revenue);
    const units = data.map(d => d.total_units);

    const ctx = document.getElementById("chart-sales-trend").getContext("2d");
    if (chartInstances.salesTrend) chartInstances.salesTrend.destroy();

    chartInstances.salesTrend = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Daily Revenue (₹)",
            data: revenues,
            borderColor: "#6366f1",
            backgroundColor: "rgba(99, 102, 241, 0.15)",
            fill: true,
            tension: 0.35,
            borderWidth: 2.5,
            pointRadius: 2,
            pointHoverRadius: 6,
            yAxisID: "y"
          },
          {
            label: "Units Sold",
            data: units,
            borderColor: "#06b6d4",
            backgroundColor: "transparent",
            borderDash: [4, 4],
            tension: 0.3,
            borderWidth: 2,
            pointRadius: 1,
            yAxisID: "y1"
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            labels: { color: "#94a3b8", font: { family: "'Plus Jakarta Sans'" } }
          }
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: { color: "#64748b", maxTicksLimit: 10 }
          },
          y: {
            type: "linear",
            position: "left",
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: {
              color: "#94a3b8",
              callback: val => `₹${val >= 1000 ? (val/1000).toFixed(0) + 'k' : val}`
            }
          },
          y1: {
            type: "linear",
            position: "right",
            grid: { drawOnChartArea: false },
            ticks: { color: "#06b6d4" }
          }
        }
      }
    });
  } catch (err) {
    console.error("Error loading sales trend chart:", err);
  }
}

// Chart 2: Top 5 Products Bar Chart
async function loadTopProductsChart(queryParam) {
  try {
    const res = await fetch(`/api/charts/top-products${queryParam}`);
    const data = await res.json();

    const labels = data.map(d => d.product_name.length > 20 ? d.product_name.slice(0, 18) + '...' : d.product_name);
    const revenues = data.map(d => d.total_revenue);

    const ctx = document.getElementById("chart-top-products").getContext("2d");
    if (chartInstances.topProducts) chartInstances.topProducts.destroy();

    chartInstances.topProducts = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: "30d Revenue (₹)",
          data: revenues,
          backgroundColor: [
            "#6366f1",
            "#8b5cf6",
            "#06b6d4",
            "#10b981",
            "#f59e0b"
          ],
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: "#94a3b8", font: { size: 10 } }
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: {
              color: "#64748b",
              callback: val => `₹${val >= 1000 ? (val/1000).toFixed(0) + 'k' : val}`
            }
          }
        }
      }
    });
  } catch (err) {
    console.error("Error loading top products chart:", err);
  }
}

// Chart 3: Stock Levels vs Safety Buffer
async function loadStockLevelsChart(queryParam) {
  try {
    const res = await fetch(`/api/charts/stock-levels${queryParam}`);
    const data = await res.json();
    const top10 = data.slice(0, 8);

    const labels = top10.map(d => d.product_name);
    const stocks = top10.map(d => d.current_stock);
    const safeties = top10.map(d => d.safety_stock);

    const ctx = document.getElementById("chart-stock-levels").getContext("2d");
    if (chartInstances.stockLevels) chartInstances.stockLevels.destroy();

    chartInstances.stockLevels = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Current Stock",
            data: stocks,
            backgroundColor: top10.map(d => d.status === 'LOW_STOCK' ? '#f43f5e' : (d.status === 'OVERSTOCK' ? '#f59e0b' : '#3b82f6')),
            borderRadius: 4
          },
          {
            label: "Safety Stock Buffer (7d)",
            data: safeties,
            backgroundColor: "rgba(255, 255, 255, 0.15)",
            borderRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#94a3b8" } }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: "#94a3b8", font: { size: 10 } }
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: { color: "#64748b" }
          }
        }
      }
    });
  } catch (err) {
    console.error("Error loading stock levels chart:", err);
  }
}

// Chart 4: Sales by Category Doughnut
async function loadCategoryChart(queryParam) {
  try {
    const res = await fetch(`/api/sales/categories${queryParam}`);
    const data = await res.json();

    const labels = data.map(d => d.category);
    const revenues = data.map(d => d.total_revenue);

    const ctx = document.getElementById("chart-category").getContext("2d");
    if (chartInstances.category) chartInstances.category.destroy();

    chartInstances.category = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [{
          data: revenues,
          backgroundColor: ["#6366f1", "#10b981", "#f59e0b", "#06b6d4", "#ec4899"],
          borderWidth: 2,
          borderColor: "#131d31"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: { color: "#94a3b8", font: { size: 11 } }
          }
        },
        cutout: "68%"
      }
    });
  } catch (err) {
    console.error("Error loading category chart:", err);
  }
}

// -------------------------------------------------------------
// ALERTS & RECOMMENDATIONS
// -------------------------------------------------------------
async function loadAlertsData() {
  const queryParam = currentStoreId ? `?store_id=${currentStoreId}` : "";
  try {
    const res = await fetch(`/api/alerts${queryParam}`);
    allAlertsData = await res.json();

    // 1. Render Top Attention Alerts on Dashboard
    renderTopDashboardAlerts(allAlertsData.slice(0, 3));

    // 2. Render Full Alerts Feed
    renderAllAlertsFeed(allAlertsData);
  } catch (err) {
    console.error("Error loading alerts:", err);
  }
}

function renderTopDashboardAlerts(alerts) {
  const container = document.getElementById("top-alerts-container");
  if (!alerts || alerts.length === 0) {
    container.innerHTML = '<div class="alert-item-card">All products are healthy and adequately stocked.</div>';
    return;
  }

  container.innerHTML = alerts.map(a => `
    <div class="alert-item-card">
      <div class="alert-item-header">
        <span class="alert-item-title">${a.product_name}</span>
        <span class="badge badge-${a.severity.toLowerCase()}">${a.severity}</span>
      </div>
      <p class="alert-item-finding">${a.finding}</p>
      <div class="alert-numbers-strip">
        <span>Stock: <strong>${a.supporting_numbers.current_stock ?? 'N/A'}</strong></span>
        <span>Daily Run: <strong>${a.supporting_numbers.avg_daily_sales ?? a.supporting_numbers.recent_avg_daily_sales ?? 'N/A'}/d</strong></span>
        ${a.supporting_numbers.days_of_stock ? `<span>Days: <strong>${a.supporting_numbers.days_of_stock}d</strong></span>` : ''}
      </div>
      <div class="alert-item-action">
        <strong>Action:</strong> ${a.recommended_action}
      </div>
    </div>
  `).join("");
}

function renderAllAlertsFeed(alerts) {
  const container = document.getElementById("all-alerts-container");
  if (!alerts || alerts.length === 0) {
    container.innerHTML = '<div class="loading-spinner">No alerts found matching the current filter.</div>';
    return;
  }

  container.innerHTML = alerts.map(a => `
    <div class="alert-full-card ${a.severity.toLowerCase()}">
      <div class="alert-full-header">
        <span class="alert-full-title">${a.product_name}</span>
        <span class="badge badge-${a.severity.toLowerCase()}">${a.alert_type} &bull; ${a.severity}</span>
      </div>
      <div class="alert-full-finding">${a.finding}</div>
      <div class="alert-full-numbers">
        <div class="num-stat-item">
          <span>Current Stock</span>
          <strong>${a.supporting_numbers.current_stock ?? 'N/A'} units</strong>
        </div>
        <div class="num-stat-item">
          <span>Run Rate</span>
          <strong>${a.supporting_numbers.avg_daily_sales ?? a.supporting_numbers.recent_avg_daily_sales ?? 'N/A'} units/day</strong>
        </div>
        <div class="num-stat-item">
          <span>Days of Supply</span>
          <strong>${a.supporting_numbers.days_of_stock ? a.supporting_numbers.days_of_stock + ' days' : 'N/A'}</strong>
        </div>
      </div>
      <div class="alert-full-assumption">
        <strong>Assumption:</strong> ${a.assumption}
      </div>
      <div class="alert-full-action">
        <strong>Recommendation:</strong> ${a.recommended_action}
      </div>
    </div>
  `).join("");
}

function filterAlerts() {
  const typeFilter = document.getElementById("alert-filter-type").value;
  const sevFilter = document.getElementById("alert-filter-severity").value;

  let filtered = allAlertsData;
  if (typeFilter !== "ALL") {
    filtered = filtered.filter(a => a.alert_type === typeFilter);
  }
  if (sevFilter !== "ALL") {
    filtered = filtered.filter(a => a.severity === sevFilter);
  }
  renderAllAlertsFeed(filtered);
}

// -------------------------------------------------------------
// INVENTORY CATALOGUE TABLE
// -------------------------------------------------------------
async function loadInventoryData() {
  const queryParam = currentStoreId ? `?store_id=${currentStoreId}` : "";
  try {
    const res = await fetch(`/api/products${queryParam}`);
    allInventoryData = await res.json();

    // Populate category dropdown
    const categories = Array.from(new Set(allInventoryData.map(p => p.category)));
    const catSelect = document.getElementById("inventory-category-filter");
    catSelect.innerHTML = '<option value="ALL">All Categories</option>';
    categories.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      catSelect.appendChild(opt);
    });

    renderInventoryTable(allInventoryData);
  } catch (err) {
    console.error("Error loading inventory table:", err);
  }
}

function renderInventoryTable(products) {
  const tbody = document.getElementById("inventory-table-body");
  if (!products || products.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center">No products matching filters.</td></tr>';
    return;
  }

  tbody.innerHTML = products.map(p => `
    <tr>
      <td>
        <strong>${p.product_name}</strong>
        <div style="font-size:0.75rem; color:#64748b;">${p.product_id} &bull; ${p.supplier}</div>
      </td>
      <td>${p.category}</td>
      <td>₹${p.price.toFixed(2)}</td>
      <td><strong>${p.current_stock}</strong></td>
      <td>${p.avg_daily_sales_7d}/day</td>
      <td>${p.units_sold_30d} units (₹${p.revenue_30d.toLocaleString('en-IN')})</td>
      <td><strong>${p.days_of_stock_display}</strong></td>
      <td><span class="status-tag status-${p.status}">${p.status.replace('_', ' ')}</span></td>
    </tr>
  `).join("");
}

function filterInventoryTable() {
  const query = document.getElementById("inventory-search").value.toLowerCase();
  const cat = document.getElementById("inventory-category-filter").value;
  const status = document.getElementById("inventory-status-filter").value;

  let filtered = allInventoryData.filter(p => {
    const matchesQuery = p.product_name.toLowerCase().includes(query) || p.product_id.toLowerCase().includes(query);
    const matchesCat = (cat === "ALL" || p.category === cat);
    const matchesStatus = (status === "ALL" || p.status === status);
    return matchesQuery && matchesCat && matchesStatus;
  });

  renderInventoryTable(filtered);
}

// -------------------------------------------------------------
// CONFIG RULES MODAL
// -------------------------------------------------------------
async function loadConfigData() {
  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();
    document.getElementById("cfg-low-stock").value = cfg.low_stock_days_threshold;
    document.getElementById("cfg-overstock").value = cfg.overstock_days_threshold;
    document.getElementById("cfg-slow-moving").value = cfg.slow_moving_daily_sales;
    document.getElementById("cfg-spike").value = cfg.spike_ratio_threshold;
  } catch (err) {
    console.error("Error loading config:", err);
  }
}

function openConfigModal() {
  document.getElementById("config-modal").classList.add("open");
}

function closeConfigModal() {
  document.getElementById("config-modal").classList.remove("open");
}

async function saveConfig() {
  const body = {
    low_stock_days_threshold: parseFloat(document.getElementById("cfg-low-stock").value),
    overstock_days_threshold: parseFloat(document.getElementById("cfg-overstock").value),
    slow_moving_daily_sales: parseFloat(document.getElementById("cfg-slow-moving").value),
    spike_ratio_threshold: parseFloat(document.getElementById("cfg-spike").value)
  };

  try {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    if (res.ok) {
      closeConfigModal();
      // Reload alerts and dashboard
      loadDashboardData();
      loadAlertsData();
      loadInventoryData();
    }
  } catch (err) {
    console.error("Error saving config:", err);
  }
}

// -------------------------------------------------------------
// COPILOT CHAT INTERFACE (STAGE 5 & 6)
// -------------------------------------------------------------
function askQuestion(q) {
  const input = document.getElementById("copilot-input");
  input.value = q;
  handleChatSubmit(new Event("submit"));
}

async function handleChatSubmit(e) {
  if (e) e.preventDefault();
  const input = document.getElementById("copilot-input");
  const question = input.value.trim();
  if (!question) return;

  // Append user message
  appendUserMessage(question);
  input.value = "";

  // Append temporary loading message
  const loadingId = "msg-loading-" + Date.now();
  appendLoadingMessage(loadingId);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, store_id: currentStoreId || null })
    });
    const data = await res.json();
    removeLoadingMessage(loadingId);
    appendBotResponse(data);
  } catch (err) {
    removeLoadingMessage(loadingId);
    appendBotError("Failed to reach Copilot engine. Please verify the backend server is running.");
  }
}

function appendUserMessage(text) {
  const container = document.getElementById("chat-messages-container");
  const msg = document.createElement("div");
  msg.className = "message-card message-user";
  msg.innerHTML = `
    <div class="message-header">
      <span class="sender-name">Store Manager</span>
      <span class="message-time">Just now</span>
    </div>
    <div class="message-body">${escapeHtml(text)}</div>
  `;
  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
}

function appendLoadingMessage(id) {
  const container = document.getElementById("chat-messages-container");
  const msg = document.createElement("div");
  msg.id = id;
  msg.className = "message-card message-bot";
  msg.innerHTML = `
    <div class="message-header">
      <span class="sender-name">Copilot Intelligence</span>
      <span class="message-time">Analyzing database...</span>
    </div>
    <div class="message-body">
      <em>Querying SQLite records and calculating deterministic metrics...</em>
    </div>
  `;
  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
}

function removeLoadingMessage(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function appendBotError(errText) {
  const container = document.getElementById("chat-messages-container");
  const msg = document.createElement("div");
  msg.className = "message-card message-bot";
  msg.innerHTML = `
    <div class="message-header">
      <span class="sender-name">Copilot Error</span>
    </div>
    <div class="message-body" style="color: #f43f5e;">${escapeHtml(errText)}</div>
  `;
  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
}

function appendBotResponse(data) {
  const container = document.getElementById("chat-messages-container");
  const msg = document.createElement("div");
  msg.className = "message-card message-bot";

  let recsHtml = "";
  if (data.recommendations && data.recommendations.length > 0) {
    recsHtml = `
      <div class="recommendations-wrapper">
        ${data.recommendations.map(r => `
          <div class="rec-card">
            <div class="rec-title">${r.finding}</div>
            <div class="rec-assumption"><strong>Assumption:</strong> ${r.assumption}</div>
            <div class="rec-action"><strong>Action:</strong> ${r.recommended_action}</div>
          </div>
        `).join("")}
      </div>
    `;
  }

  let dataUsedHtml = "";
  if (data.data_used) {
    const keys = Object.keys(data.data_used);
    if (keys.length > 0) {
      dataUsedHtml = `
        <div class="data-used-box">
          <div class="data-used-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            Data Used (Grounding Evidence)
          </div>
          <div>${JSON.stringify(data.data_used, null, 2)}</div>
        </div>
      `;
    }
  }

  msg.innerHTML = `
    <div class="message-header">
      <span class="sender-name">Copilot Intelligence</span>
      <span class="message-time">Source: ${data.source || 'Deterministic Engine'}</span>
    </div>
    <div class="copilot-answer-text">${formatMarkdownText(data.answer)}</div>
    ${recsHtml}
    ${dataUsedHtml}
  `;

  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
}

function formatMarkdownText(text) {
  if (!text) return "";
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}

function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return text.replace(/[&<>"']/g, m => map[m]);
}
