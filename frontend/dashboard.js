const express = require('express');
const router = express.Router();

// Set via docker-compose.yml -> resolves to the backend container over
// Docker's internal network. Never hardcode this.
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:5000';

// Same cookie Story 7's auth.js sets on login/signup.
const TOKEN_COOKIE = 'fg_token';

const MACROS = [
    { key: 'calories', targetKey: 'calories', label: 'Calories', unit: 'kcal' },
    { key: 'protein', targetKey: 'protein_g', label: 'Protein', unit: 'g' },
    { key: 'carbs', targetKey: 'carbs_g', label: 'Carbs', unit: 'g' },
    { key: 'fats', targetKey: 'fats_g', label: 'Fats', unit: 'g' },
];

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
}

// Safe to embed inside a <script> block: JSON.stringify alone would let a
// literal "</script>" in the data close the tag early.
function toInlineJson(value) {
    return JSON.stringify(value).replace(/</g, '\\u003c');
}

function decodeTokenPayload(token) {
    try {
        const payloadSegment = token.split('.')[1];
        const json = Buffer.from(payloadSegment, 'base64url').toString('utf-8');
        return JSON.parse(json);
    } catch (err) {
        console.error(err);
        return null;
    }
}

function pageShell(title, bodyHtml, extraHead = '') {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)} · Food Gorilla</title>
  <link rel="stylesheet" href="/css/style.css">
  ${extraHead}
</head>
<body>
${bodyHtml}
</body>
</html>`;
}

function requireUserToken(req, res) {
    const token = req.cookies[TOKEN_COOKIE];
    const payload = token && decodeTokenPayload(token);
    if (!payload) {
        res.redirect('/login');
        return null;
    }
    return token;
}

async function backendFetch(token, path, options = {}) {
    return fetch(`${BACKEND_URL}${path}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            ...(options.headers || {}),
        },
    });
}

// Page-specific styling for the progress bars, alerts, weekly stats and
// chart cards. Kept scoped to this page (rather than added to the shared
// stylesheet) so it can't collide with other stories' edits to
// public/css/style.css.
const DASHBOARD_STYLES = `<style>
  .dashboard-bars { display: grid; gap: 22px; margin-top: 10px; }
  .macro-bar-row { display: grid; gap: 8px; }
  .macro-bar-label { display: flex; justify-content: space-between; font-weight: 600; color: #4b371f; }
  .macro-bar-label .macro-bar-amounts { font-weight: 500; color: #7b5b42; }
  .macro-bar-track { background: #f3e3d0; border-radius: 999px; height: 18px; overflow: hidden; }
  .macro-bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #f56a28 0%, #f4b32f 100%); transition: width 0.3s ease; }
  .macro-bar-fill.exceeded { background: linear-gradient(90deg, #d13b2f 0%, #f0574a 100%); }
  .macro-bar-warning { margin-top: 4px; font-size: 0.9rem; color: #a83e2c; font-weight: 600; }
  .dashboard-section { margin-top: 32px; }
  .dashboard-toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 4px; }
  .dashboard-card { border: 1px solid #f3d8c1; background: #fff7f2; border-radius: 20px; padding: 24px; margin-top: 20px; }
  .dashboard-alerts { display: grid; gap: 10px; margin-top: 18px; }
  .auth-message.warning { display: block; background: #fdf1e0; color: #8a5a12; }
  .weekly-stats { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 20px; }
  .weekly-stats .account-stat { flex: 1; min-width: 180px; }
  .chart-wrap { position: relative; height: 260px; margin-top: 12px; }
</style>`;

function renderBar(macroDef, targets, consumed, exceeded) {
    const target = targets[macroDef.targetKey];
    const amount = consumed[macroDef.key];
    const pct = target > 0 ? Math.min(100, Math.round((amount / target) * 100)) : 0;
    const isExceeded = exceeded[macroDef.key];

    return `
      <div class="macro-bar-row">
        <div class="macro-bar-label">
          <span>${macroDef.label}</span>
          <span class="macro-bar-amounts">${amount} / ${target} ${macroDef.unit}</span>
        </div>
        <div class="macro-bar-track">
          <div class="macro-bar-fill${isExceeded ? ' exceeded' : ''}" style="width: ${pct}%"></div>
        </div>
        ${isExceeded ? `<div class="macro-bar-warning">Over your daily ${macroDef.label.toLowerCase()} target by ${amount - target} ${macroDef.unit}</div>` : ''}
      </div>`;
}

function renderAlerts(targets, consumed, exceeded) {
    const alerts = [];
    for (const m of MACROS) {
        const target = targets[m.targetKey];
        const amount = consumed[m.key];
        if (exceeded[m.key]) {
            alerts.push(`<div class="auth-message error">${m.label} exceeded target by ${amount - target} ${m.unit}.</div>`);
        } else if (target > 0 && Math.round((amount / target) * 100) >= 75) {
            alerts.push(`<div class="auth-message warning">${m.label} is approaching target.</div>`);
        }
    }
    if (!alerts.length) {
        return '<p class="empty-state">Nothing to flag yet — you\'re comfortably within every target.</p>';
    }
    return `<div class="dashboard-alerts">${alerts.join('')}</div>`;
}

function renderWeeklyStats(summary) {
    if (!summary.days_logged) {
        return '<p class="empty-state">No logged days yet — place an order to start building your weekly history.</p>';
    }
    return `
      <div class="weekly-stats">
        <div class="account-stat"><span>🔥</span><div><strong>Average Calories/Day</strong>${summary.average_calories} kcal</div></div>
        <div class="account-stat"><span>✅</span><div><strong>Days On Track</strong>${summary.days_on_track} / ${summary.days_logged}</div></div>
        <div class="account-stat"><span>⚠️</span><div><strong>Times Exceeded</strong>${summary.times_exceeded} / ${summary.days_logged}</div></div>
      </div>`;
}

function renderCharts(consumed, weeklyDays) {
    const chartData = toInlineJson({ consumed, weeklyDays });
    return `
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
    <script>
      const dashboardChartData = ${chartData};
      const macroPalette = ['#a95c24', '#f56a28', '#f4b32f'];

      new Chart(document.getElementById('macroPieChart'), {
        type: 'pie',
        data: {
          labels: ['Protein (g)', 'Carbs (g)', 'Fats (g)'],
          datasets: [{
            data: [dashboardChartData.consumed.protein, dashboardChartData.consumed.carbs, dashboardChartData.consumed.fats],
            backgroundColor: macroPalette,
            borderColor: '#fff7f2',
            borderWidth: 2,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom' } },
        },
      });

      if (dashboardChartData.weeklyDays.length) {
        new Chart(document.getElementById('weeklyBarChart'), {
          type: 'bar',
          data: {
            labels: dashboardChartData.weeklyDays.map((d) => d.date),
            datasets: [{
              label: 'Calories',
              data: dashboardChartData.weeklyDays.map((d) => d.calories),
              backgroundColor: dashboardChartData.weeklyDays.map((d) => (d.exceeded ? '#d13b2f' : '#f56a28')),
              borderRadius: 6,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, title: { display: true, text: 'Calories (kcal)' } } },
          },
        });
      }
    </script>`;
}

router.get('/dashboard', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    try {
        const backendRes = await backendFetch(token, '/dashboard');
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.status(backendRes.status).send(pageShell('Dashboard', `<p>${escapeHtml(data.error || 'Failed to load your dashboard.')}</p>`));
        }

        const nav = `
      <div class="auth-nav">
        <a class="nav-link" href="/profile">Back to Profile</a>
        <a class="logout-button" href="/logout">Log Out</a>
      </div>`;

        let main;
        let chartsScript = '';
        if (!data.targets) {
            main = `
      <div class="account-hero">
        <div>
          <h1>Daily Fitness Dashboard</h1>
          <p>You haven't set a macro profile yet, so there's nothing to compare today's intake against.</p>
          <div class="hero-actions">
            <a href="/macros">Set your daily targets →</a>
          </div>
        </div>
      </div>`;
        } else {
            const weeklyRes = await backendFetch(token, '/dashboard/weekly');
            const weeklyData = weeklyRes.ok ? await weeklyRes.json() : { days: [], summary: { days_logged: 0 } };

            const barsHtml = MACROS.map((m) => renderBar(m, data.targets, data.consumed, data.exceeded)).join('');
            main = `
      <div class="account-hero">
        <div>
          <h1>Daily Fitness Dashboard</h1>
          <p>Today's progress toward your daily calorie and macro targets.</p>
        </div>
      </div>
      <main>
        <div class="dashboard-toolbar">
          <h2 class="section-label">Today's Macro Progress</h2>
          <div class="profile-actions">
            <form method="POST" action="/dashboard/reset">
              <button type="submit" class="delete-profile">Reset Today's Log</button>
            </form>
          </div>
        </div>
        <div class="dashboard-bars">${barsHtml}</div>
        ${renderAlerts(data.targets, data.consumed, data.exceeded)}

        <div class="dashboard-card">
          <h3 class="section-label">Today's Macro Split</h3>
          <div class="chart-wrap"><canvas id="macroPieChart"></canvas></div>
        </div>

        <div class="dashboard-section">
          <h2 class="section-label">Weekly Nutrition Summary</h2>
          ${renderWeeklyStats(weeklyData.summary)}
          ${weeklyData.days.length ? `
          <div class="dashboard-card">
            <h3 class="section-label">Calories This Week</h3>
            <div class="chart-wrap"><canvas id="weeklyBarChart"></canvas></div>
          </div>` : ''}
        </div>
      </main>`;
            chartsScript = renderCharts(data.consumed, weeklyData.days);
        }

        const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      ${nav}
      ${main}
    </div>
  </div>
  ${chartsScript}`;
        res.send(pageShell('Dashboard', body, DASHBOARD_STYLES));
    } catch (err) {
        res.status(502).send(pageShell('Dashboard', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

router.post('/dashboard/reset', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    try {
        const backendRes = await backendFetch(token, '/dashboard/reset', { method: 'POST' });
        if (!backendRes.ok) {
            const data = await backendRes.json();
            return res.status(backendRes.status).send(pageShell('Dashboard', `<p>${escapeHtml(data.error || "Could not reset today's log.")}</p>`));
        }
        res.redirect('/dashboard');
    } catch (err) {
        res.status(502).send(pageShell('Dashboard', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

module.exports = router;
