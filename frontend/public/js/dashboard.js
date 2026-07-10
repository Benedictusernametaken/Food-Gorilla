const dashboard = document.getElementById('dashboard');
const toastContainer = document.getElementById('toast-container');
const orderForm = document.getElementById('order-form');
const alertBanner = document.getElementById('alert-banner');
const dashboardSummary = document.getElementById('dashboard-summary');
const historyStats = document.getElementById('history-stats');
const calorieChartCanvas = document.getElementById('calorie-chart');
const submitButton = orderForm.querySelector('button[type="submit"]');
let isSubmittingOrder = false;
let calorieChart = null;

const ICONS = {
  calories: '🔥',
  protein: '🥩',
  carbs: '🥖',
  fats: '💧',
};

const META = [
  { key: 'calories', label: 'Calories', unit: 'kcal' },
  { key: 'protein', label: 'Protein', unit: 'g' },
  { key: 'carbs', label: 'Carbs', unit: 'g' },
  { key: 'fats', label: 'Fats', unit: 'g' },
];

function getBadgeText(tier) {
  if (tier === 'red') return 'Exceeded';
  if (tier === 'yellow') return 'Almost there';
  return 'On track';
}

function renderDashboard(data) {
  const onTrackCount = META.reduce((count, macro) => {
    const tier = data[macro.key]?.tier;
    return count + (tier === 'green' ? 1 : 0);
  }, 0);

  dashboardSummary.textContent = `${onTrackCount} of 4 macros on track`;
  dashboard.innerHTML = META.map((macro) => {
    const macroData = data[macro.key];
    const tier = ['green', 'yellow', 'red'].includes(macroData.tier) ? macroData.tier : 'green';
    const percent = Math.min(100, macroData.percent);
    const fillColor = tier === 'red' ? '#ef4444' : tier === 'yellow' ? '#f59e0b' : '#22c55e';
    const delta = macroData.target - macroData.consumed;
    const remainder = delta > 0
      ? `${delta}${macro.unit} left`
      : delta < 0
        ? `+${-delta}${macro.unit} over`
        : 'At target';

    return `
      <article class="macro-card">
        <h3>
          <span class="macro-label">${ICONS[macro.key]} ${macro.label}</span>
          <span class="status-badge ${tier}">${getBadgeText(tier)}</span>
        </h3>
        <div class="macro-stats">
          <span>${macroData.consumed}${macro.unit}</span>
          <span>${macroData.target}${macro.unit}</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill ${tier}" style="width: ${percent}%; background-color: ${fillColor};"></div>
        </div>
        <div class="macro-remaining">${remainder}</div>
      </article>
    `;
  }).join('');
}

function showToast(alert) {
  const toast = document.createElement('div');
  toast.className = `toast ${alert.tier}`;
  toast.textContent = alert.message;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 3800);
}

async function fetchDashboard(date) {
  const params = new URLSearchParams({ date });
  const response = await fetch(`/api/daily-log?${params.toString()}`, {
    headers: { 'X-Session-Token': getSessionToken() },
  });
  if (!response.ok) {
    console.error('Failed to load dashboard', await response.text());
    return;
  }
  const data = await response.json();
  renderDashboard(data);
  clearAlertBanner();
}

function clearAlertBanner() {
  alertBanner.hidden = true;
  alertBanner.textContent = '';
}

function renderAlertBanner(data) {
  const alertMessages = [];

  META.forEach((macro) => {
    const value = data[macro.key];
    if (!value) return;
    if (value.tier === 'red') {
      const over = value.consumed - value.target;
      if (over > 0) {
        alertMessages.push(`${macro.label} exceeded by ${over}${macro.unit} after your last order.`);
      } else {
        alertMessages.push(`${macro.label} is exactly at your daily target after your last order.`);
      }
    } else if (value.tier === 'yellow') {
      alertMessages.push(`${macro.label} is almost there at ${value.percent}% of target.`);
    }
  });

  if (alertMessages.length > 0) {
    alertBanner.hidden = false;
    alertBanner.innerHTML = alertMessages.map((message) => `<div>${message}</div>`).join('');
  } else {
    clearAlertBanner();
  }
}

function getSessionToken() {
  const cookie = document.cookie.split('; ').find((entry) => entry.startsWith('auth_token='));
  return cookie ? cookie.split('=')[1] : '';
}

async function submitOrder(event) {
  event.preventDefault();
  if (isSubmittingOrder) {
    return;
  }

  isSubmittingOrder = true;
  submitButton.disabled = true;

  const payload = {
    calories: document.getElementById('calories').value,
    protein_g: document.getElementById('protein_g').value,
    carbs_g: document.getElementById('carbs_g').value,
    fats_g: document.getElementById('fats_g').value,
  };

  const response = await fetch('/api/orders/complete', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Session-Token': getSessionToken(),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    alert(`Failed to simulate order: ${error.error || 'unknown error'}`);
    isSubmittingOrder = false;
    submitButton.disabled = false;
    return;
  }

  const result = await response.json();
  renderDashboard(result.totals);
  renderAlertBanner(result.totals);
  await fetchHistory(7);

  if (result.new_alerts && result.new_alerts.length > 0) {
    result.new_alerts.forEach(showToast);
  } else {
    showToast({
      tier: 'green',
      message: 'Order simulated successfully — dashboard updated.',
    });
  }

  isSubmittingOrder = false;
  submitButton.disabled = false;
}

async function resetTodayLog() {
  const response = await fetch('/api/daily-log/reset', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Session-Token': getSessionToken(),
    },
  });

  if (!response.ok) {
    const error = await response.json();
    alert(`Failed to reset today's log: ${error.error || 'unknown error'}`);
    return;
  }

  const today = new Date().toISOString().slice(0, 10);
  await fetchDashboard(today);
  await fetchHistory(7);
  showToast({ tier: 'green', message: 'Today\'s log has been reset.' });
}

function summarizeHistory(history) {
  const counts = { above: 0, onTarget: 0, below: 0 };

  history.forEach((entry) => {
    if (entry.consumed_calories === entry.target_calories) {
      counts.onTarget += 1;
    } else if (entry.consumed_calories > entry.target_calories) {
      counts.above += 1;
    } else {
      counts.below += 1;
    }
  });

  return counts;
}

function renderHistoryStats(history) {
  if (!history || history.length === 0) {
    historyStats.innerHTML = '<div class="history-stat"><h3>No history</h3><p>Data not available.</p></div>';
    return;
  }

  const summary = summarizeHistory(history);
  historyStats.innerHTML = [
    { label: 'Above target', value: `${summary.above}` },
    { label: 'On target', value: `${summary.onTarget}` },
    { label: 'Below target', value: `${summary.below}` },
  ].map((stat) => `
    <div class="history-stat">
      <h3>${stat.label}</h3>
      <p>${stat.value}</p>
    </div>
  `).join('');
}

function renderCalorieChart(history) {
  const labels = history.map((entry) => entry.date.slice(5));
  const calories = history.map((entry) => entry.consumed_calories);
  const targets = history.map((entry) => entry.target_calories);
  const barColors = history.map((entry) => (entry.consumed_calories > entry.target_calories ? '#f87171' : '#3b82f6'));

  const data = {
    labels,
    datasets: [
      {
        type: 'bar',
        label: 'Calories consumed',
        data: calories,
        backgroundColor: barColors,
        borderRadius: 8,
        barPercentage: 0.65,
      },
      {
        type: 'line',
        label: 'Daily target',
        data: targets,
        borderColor: '#2563eb',
        borderWidth: 2,
        pointRadius: 0,
        fill: false,
        tension: 0.1,
      },
    ],
  };

  const config = {
    data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: 'top' },
        tooltip: { callbacks: { label: (context) => `${context.dataset.label}: ${context.parsed.y} kcal` } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#475569' } },
        y: { beginAtZero: true, grid: { color: '#e2e8f0' }, ticks: { color: '#475569' } },
      },
    },
  };

  if (calorieChart) {
    calorieChart.destroy();
  }

  calorieChart = new Chart(calorieChartCanvas, config);
}

async function fetchHistory(days) {
  const params = new URLSearchParams({ days });
  const response = await fetch(`/api/daily-log/history?${params.toString()}`, {
    headers: { 'X-Session-Token': getSessionToken() },
  });
  if (!response.ok) {
    console.error('Failed to load history', await response.text());
    return;
  }

  const history = await response.json();
  renderHistoryStats(history);
  renderCalorieChart(history);
}

async function refreshUserData(date) {
  await Promise.all([
    fetchDashboard(date),
    fetchHistory(7),
  ]);
}

orderForm.addEventListener('submit', submitOrder);
const resetButton = document.getElementById('reset-button');
resetButton.addEventListener('click', resetTodayLog);

const today = new Date().toISOString().slice(0, 10);
refreshUserData(today);
