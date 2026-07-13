const express = require('express');
const router = express.Router();

// Set via docker-compose.yml -> resolves to the backend container over
// Docker's internal network. Never hardcode this.
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:5000';

// Same cookie Story 7's auth.js sets on login/signup.
const TOKEN_COOKIE = 'fg_token';

const DAYS = [
    { value: 1, label: 'Monday' },
    { value: 2, label: 'Tuesday' },
    { value: 3, label: 'Wednesday' },
    { value: 4, label: 'Thursday' },
    { value: 5, label: 'Friday' },
];
const TIME_SLOTS = ['breakfast', 'lunch', 'dinner'];

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

// Page-specific styling for the weekly planner grid and subscription
// summary cards. Kept scoped to this page (rather than added to the
// shared stylesheet) so it can't collide with other stories' edits to
// public/css/style.css.
const SUBSCRIPTIONS_STYLES = `<style>
  .planner-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .planner-day { border: 1px solid #f1d3b2; background: #fff8f2; border-radius: 16px; padding: 16px; }
  .planner-day h4 { color: #4b371f; margin-bottom: 10px; }
  .planner-day label { font-size: 0.9rem; display: block; margin-bottom: 4px; color: #5b432e; }
  .planner-day select { width: 100%; margin-bottom: 10px; }
  .planner-day .day-enable { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; font-weight: 600; }
  .planner-day .day-enable input { width: auto; }
  .sub-card { border: 1px solid #f3ceb3; background: #fff4ea; border-radius: 18px; padding: 20px 22px; margin-bottom: 20px; }
  .sub-card-header { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
  .sub-card-header h3 { color: #4b371f; }
  .sub-status { font-size: 0.85rem; font-weight: 700; color: #a95c24; text-transform: uppercase; }
  .sub-totals { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; }
  .sub-totals span { background: #f56a28; color: white; border-radius: 999px; padding: 4px 12px; font-size: 0.85rem; font-weight: 600; }
  .sub-schedule-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; padding: 10px 0; border-top: 1px solid #f3d8c1; }
  .sub-schedule-row:first-of-type { border-top: none; }
  .sub-schedule-meta { color: #5b432e; }
  .sub-schedule-actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .sub-schedule-actions form { display: flex; gap: 6px; align-items: center; }
  .sub-schedule-actions select { padding: 6px 8px; font-size: 0.85rem; }
  .sub-schedule-actions button { padding: 6px 12px; font-size: 0.85rem; }
</style>`;

function renderMealOptions(meals, selectedId) {
    return meals.map((m) => `<option value="${m.meal_id}" ${String(m.meal_id) === String(selectedId) ? 'selected' : ''}>${escapeHtml(m.name)} ($${m.price.toFixed(2)})</option>`).join('');
}

function renderTimeSlotOptions(selected) {
    return TIME_SLOTS.map((slot) => `<option value="${slot}" ${slot === selected ? 'selected' : ''}>${slot[0].toUpperCase()}${slot.slice(1)}</option>`).join('');
}

function renderPlannerForm(meals) {
    if (!meals.length) {
        return '<p class="empty-state">No meals are available to schedule yet — check back once a vendor has published their menu.</p>';
    }

    const daysHtml = DAYS.map((day) => `
      <div class="planner-day">
        <label class="day-enable"><input type="checkbox" name="day_${day.value}_enabled" value="1"> ${day.label}</label>
        <label>Meal</label>
        <select name="day_${day.value}_meal_id">${renderMealOptions(meals)}</select>
        <label>Delivery time</label>
        <select name="day_${day.value}_time_slot">${renderTimeSlotOptions('lunch')}</select>
      </div>`).join('');

    return `
      <form method="POST" action="/subscriptions">
        <div class="form-group">
          <label>Start date</label>
          <input type="date" name="start_date" required>
        </div>
        <div class="form-group">
          <label>End date</label>
          <input type="date" name="end_date" required>
        </div>
        <div class="planner-grid">${daysHtml}</div>
        <button type="submit" class="btn-submit">Create Weekly Plan</button>
      </form>`;
}

function renderScheduleRow(subscriptionId, meals, item) {
    return `
    <div class="sub-schedule-row">
      <div class="sub-schedule-meta">
        <strong>${escapeHtml(item.day_name)}</strong> · ${escapeHtml(item.time_slot)} —
        ${escapeHtml(item.meal_name)} (${item.calories} kcal, $${item.price.toFixed(2)})
      </div>
      <div class="sub-schedule-actions">
        <form method="POST" action="/subscriptions/${subscriptionId}/schedule/${item.schedule_id}/modify">
          <select name="meal_id">${renderMealOptions(meals, item.meal_id)}</select>
          <select name="time_slot">${renderTimeSlotOptions(item.time_slot)}</select>
          <button type="submit">Update</button>
        </form>
        <form method="POST" action="/subscriptions/${subscriptionId}/schedule/${item.schedule_id}/cancel">
          <button type="submit" class="delete-profile">Cancel</button>
        </form>
      </div>
    </div>`;
}

function renderSubscriptionCard(sub, meals) {
    const scheduleHtml = sub.schedule.length
        ? sub.schedule.map((item) => renderScheduleRow(sub.subscription_id, meals, item)).join('')
        : '<p class="empty-state">No days scheduled on this plan.</p>';

    return `
    <div class="sub-card">
      <div class="sub-card-header">
        <h3>${escapeHtml(sub.start_date)} → ${escapeHtml(sub.end_date)}</h3>
        <span class="sub-status">${escapeHtml(sub.status)}</span>
      </div>
      <div class="sub-totals">
        <span>$${sub.total_cost.toFixed(2)} / week</span>
        <span>${sub.total_calories} kcal</span>
        <span>${sub.total_protein}g protein</span>
        <span>${sub.total_carbs}g carbs</span>
        <span>${sub.total_fats}g fats</span>
      </div>
      ${scheduleHtml}
    </div>`;
}

async function loadMeals(token) {
    const res = await backendFetch(token, '/menu');
    if (!res.ok) return [];
    const data = await res.json();
    return data.meals || [];
}

router.get('/subscriptions', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    try {
        const [subsRes, meals] = await Promise.all([
            backendFetch(token, '/subscriptions'),
            loadMeals(token),
        ]);
        const subsData = await subsRes.json();

        if (!subsRes.ok) {
            return res.status(subsRes.status).send(pageShell('Subscriptions', `<p>${escapeHtml(subsData.error || 'Failed to load your subscriptions.')}</p>`));
        }

        const subsHtml = subsData.subscriptions.length
            ? subsData.subscriptions.map((sub) => renderSubscriptionCard(sub, meals)).join('')
            : '<p class="empty-state">No weekly plans yet — build one below.</p>';

        const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="auth-nav">
        <a class="nav-link" href="/profile">Back to Profile</a>
        <a class="logout-button" href="/logout">Log Out</a>
      </div>
      <div class="account-hero">
        <div>
          <h1>Weekly Meal Plan</h1>
          <p>Schedule recurring meal deliveries for Monday through Friday and see the weekly cost and macro total.</p>
        </div>
      </div>
      <main>
        ${req.query.error ? `<div class="auth-message error">${escapeHtml(req.query.error)}</div>` : ''}
        <h2 class="section-label">Your Plans</h2>
        ${subsHtml}
        <h2 class="section-label">Build a New Plan</h2>
        ${renderPlannerForm(meals)}
      </main>
    </div>
  </div>`;
        res.send(pageShell('Weekly Meal Plan', body, SUBSCRIPTIONS_STYLES));
    } catch (err) {
        res.status(502).send(pageShell('Subscriptions', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

router.post('/subscriptions', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    const { start_date, end_date } = req.body;
    const schedule = DAYS
        .filter((day) => req.body[`day_${day.value}_enabled`])
        .map((day) => ({
            day_of_week: day.value,
            meal_id: parseInt(req.body[`day_${day.value}_meal_id`], 10),
            time_slot: req.body[`day_${day.value}_time_slot`],
        }));

    if (!schedule.length) {
        return res.redirect('/subscriptions?error=' + encodeURIComponent('Select at least one day to schedule.'));
    }

    try {
        const backendRes = await backendFetch(token, '/subscriptions', {
            method: 'POST',
            body: JSON.stringify({ start_date, end_date, schedule }),
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.redirect('/subscriptions?error=' + encodeURIComponent(data.error || 'Could not create the weekly plan.'));
        }

        res.redirect('/subscriptions');
    } catch (err) {
        res.status(502).send(pageShell('Subscriptions', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

router.post('/subscriptions/:id/schedule/:scheduleId/modify', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    const { meal_id, time_slot } = req.body;

    try {
        const backendRes = await backendFetch(token, `/subscriptions/${req.params.id}/schedule/${req.params.scheduleId}`, {
            method: 'PUT',
            body: JSON.stringify({ meal_id: parseInt(meal_id, 10), time_slot }),
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.redirect('/subscriptions?error=' + encodeURIComponent(data.error || 'Could not update that scheduled meal.'));
        }

        res.redirect('/subscriptions');
    } catch (err) {
        res.status(502).send(pageShell('Subscriptions', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

router.post('/subscriptions/:id/schedule/:scheduleId/cancel', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    try {
        const backendRes = await backendFetch(token, `/subscriptions/${req.params.id}/schedule/${req.params.scheduleId}`, {
            method: 'DELETE',
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.redirect('/subscriptions?error=' + encodeURIComponent(data.error || 'Could not cancel that scheduled meal.'));
        }

        res.redirect('/subscriptions');
    } catch (err) {
        res.status(502).send(pageShell('Subscriptions', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

module.exports = router;
