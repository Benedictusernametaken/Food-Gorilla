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

function decodeTokenPayload(token) {
    try {
        const payloadSegment = token.split('.')[1];
        const json = Buffer.from(payloadSegment, 'base64url').toString('utf-8');
        return JSON.parse(json);
    } catch (err) {
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

// Page-specific styling for the progress bars. Kept scoped to this page
// (rather than added to the shared stylesheet) so it can't collide with
// other stories' edits to public/css/style.css.
const DASHBOARD_STYLES = `<style>
  .dashboard-bars { display: grid; gap: 22px; margin-top: 10px; }
  .macro-bar-row { display: grid; gap: 8px; }
  .macro-bar-label { display: flex; justify-content: space-between; font-weight: 600; color: #4b371f; }
  .macro-bar-label .macro-bar-amounts { font-weight: 500; color: #7b5b42; }
  .macro-bar-track { background: #f3e3d0; border-radius: 999px; height: 18px; overflow: hidden; }
  .macro-bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #f56a28 0%, #f4b32f 100%); transition: width 0.3s ease; }
  .macro-bar-fill.exceeded { background: linear-gradient(90deg, #d13b2f 0%, #f0574a 100%); }
  .macro-bar-warning { margin-top: 4px; font-size: 0.9rem; color: #a83e2c; font-weight: 600; }
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
        if (!data.targets) {
            main = `
      <div class="account-hero">
        <div>
          <h1>Daily Fitness Dashboard</h1>
          <p>You haven't set a macro profile yet, so there's nothing to compare today's intake against.</p>
          <p><a href="/macros">Set your daily targets →</a></p>
        </div>
      </div>`;
        } else {
            const barsHtml = MACROS.map((m) => renderBar(m, data.targets, data.consumed, data.exceeded)).join('');
            main = `
      <div class="account-hero">
        <div>
          <h1>Daily Fitness Dashboard</h1>
          <p>Today's progress toward your daily calorie and macro targets.</p>
        </div>
      </div>
      <main>
        <div class="dashboard-bars">${barsHtml}</div>
      </main>`;
        }

        const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      ${nav}
      ${main}
    </div>
  </div>`;
        res.send(pageShell('Dashboard', body, DASHBOARD_STYLES));
    } catch (err) {
        res.status(502).send(pageShell('Dashboard', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

module.exports = router;
