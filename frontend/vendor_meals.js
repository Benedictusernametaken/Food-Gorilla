const express = require('express');
const router = express.Router();

// Set via docker-compose.yml -> resolves to the backend container over
// Docker's internal network. Never hardcode this.
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:5000';

// Same cookie Story 8's vendor_auth.js sets on login/signup.
const VENDOR_TOKEN_COOKIE = 'fg_vendor_token';

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
}

// Decodes the JWT payload for display purposes only (e.g. showing the
// logged-in restaurant name, deciding whether to redirect to login). The
// signature is never checked here — every backend call below sends the raw
// token and lets the backend be the actual trust boundary.
function decodeTokenPayload(token) {
    try {
        const payloadSegment = token.split('.')[1];
        const json = Buffer.from(payloadSegment, 'base64url').toString('utf-8');
        return JSON.parse(json);
    } catch (err) {
        return null;
    }
}

function pageShell(title, bodyHtml) {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)} · Food Gorilla</title>
  <link rel="stylesheet" href="/css/style.css">
</head>
<body>
${bodyHtml}
</body>
</html>`;
}

function requireVendorToken(req, res) {
    const token = req.cookies[VENDOR_TOKEN_COOKIE];
    const payload = token && decodeTokenPayload(token);
    if (!payload) {
        res.redirect('/vendor/login');
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

function renderMealRow(meal) {
    const statusLabel = meal.is_available ? 'In Stock' : 'Out of Stock';
    const toggleLabel = meal.is_available ? 'Mark Out of Stock' : 'Mark In Stock';
    return `
    <div class="saved-profile-item">
      <div class="profile-meta">
        <div class="profile-name">${escapeHtml(meal.name)} — $${meal.price.toFixed(2)}</div>
        <div class="profile-date">${meal.calories} kcal · ${meal.protein}g protein · ${meal.carbs}g carbs · ${meal.fats}g fats</div>
        <div class="profile-date">Status: ${statusLabel}</div>
      </div>
      <div class="profile-actions">
        <a class="nav-link" href="/vendor/meals/${meal.meal_id}/edit">Edit</a>
        <form method="POST" action="/vendor/meals/${meal.meal_id}/toggle" style="display:inline">
          <button type="submit">${toggleLabel}</button>
        </form>
        <form method="POST" action="/vendor/meals/${meal.meal_id}/delete" style="display:inline">
          <button type="submit" class="delete-profile">Delete</button>
        </form>
      </div>
    </div>`;
}

function renderMealForm({ action, meal, error } = {}) {
    return `
          <form method="POST" action="${action}">
            <div class="form-group">
              <label>Name</label>
              <input type="text" name="name" value="${escapeHtml(meal?.name)}" required>
            </div>
            <div class="form-group">
              <label>Description</label>
              <input type="text" name="description" value="${escapeHtml(meal?.description)}">
            </div>
            <div class="form-group">
              <label>Price ($)</label>
              <input type="number" step="0.01" min="0" name="price" value="${meal ? meal.price : ''}" required>
            </div>
            <div class="form-group">
              <label>Calories</label>
              <input type="number" min="0" name="calories" value="${meal ? meal.calories : ''}" required>
            </div>
            <div class="form-group">
              <label>Protein (g)</label>
              <input type="number" min="0" name="protein" value="${meal ? meal.protein : ''}" required>
            </div>
            <div class="form-group">
              <label>Carbs (g)</label>
              <input type="number" min="0" name="carbs" value="${meal ? meal.carbs : ''}" required>
            </div>
            <div class="form-group">
              <label>Fats (g)</label>
              <input type="number" min="0" name="fats" value="${meal ? meal.fats : ''}" required>
            </div>
            <button type="submit" class="btn-submit">${meal ? 'Save Changes' : 'Add Menu Item'}</button>
          </form>
          ${error ? `<div class="auth-message error">${escapeHtml(error)}</div>` : ''}`;
}

router.get('/vendor/meals', async (req, res) => {
    const token = requireVendorToken(req, res);
    if (!token) return;

    try {
        const backendRes = await backendFetch(token, '/vendor/meals');
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.status(backendRes.status).send(pageShell('Menu Management', `<p>${escapeHtml(data.error || 'Failed to load meals.')}</p>`));
        }

        const mealsHtml = data.meals.length
            ? data.meals.map(renderMealRow).join('')
            : '<p class="empty-state">No menu items yet — add your first one below.</p>';

        const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="auth-nav">
        <a class="nav-link" href="/vendor/portal">Back to Portal</a>
        <a class="logout-button" href="/vendor/logout">Log Out</a>
      </div>
      <div class="account-hero">
        <h1>Your Menu Items</h1>
      </div>
      <div class="saved-profiles-section">
        <div class="saved-profiles-list">${mealsHtml}</div>
      </div>
      <div class="account-update-card" style="margin-top: 28px;">
        <h2>Add a menu item</h2>
        ${renderMealForm({ action: '/vendor/meals' })}
      </div>
    </div>
  </div>`;
        res.send(pageShell('Menu Management', body));
    } catch (err) {
        res.status(502).send(pageShell('Menu Management', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

router.post('/vendor/meals', async (req, res) => {
    const token = requireVendorToken(req, res);
    if (!token) return;

    const { name, description, price, calories, protein, carbs, fats } = req.body;

    try {
        const backendRes = await backendFetch(token, '/vendor/meals', {
            method: 'POST',
            body: JSON.stringify({ name, description, price, calories, protein, carbs, fats }),
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="account-update-card">
        <h2>Add a menu item</h2>
        ${renderMealForm({ action: '/vendor/meals', meal: { name, description, price, calories, protein, carbs, fats }, error: data.error })}
      </div>
    </div>
  </div>`;
            return res.status(backendRes.status).send(pageShell('Menu Management', body));
        }

        res.redirect('/vendor/meals');
    } catch (err) {
        res.status(502).send(pageShell('Menu Management', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

router.get('/vendor/meals/:id/edit', async (req, res) => {
    const token = requireVendorToken(req, res);
    if (!token) return;

    try {
        const backendRes = await backendFetch(token, `/vendor/meals/${req.params.id}`);
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.status(backendRes.status).send(pageShell('Edit Menu Item', `<p>${escapeHtml(data.error || 'Meal not found.')}</p>`));
        }

        const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="auth-nav">
        <a class="nav-link" href="/vendor/meals">Back to Menu</a>
      </div>
      <div class="account-update-card">
        <h2>Edit ${escapeHtml(data.name)}</h2>
        ${renderMealForm({ action: `/vendor/meals/${data.meal_id}`, meal: data })}
      </div>
    </div>
  </div>`;
        res.send(pageShell('Edit Menu Item', body));
    } catch (err) {
        res.status(502).send(pageShell('Edit Menu Item', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

router.post('/vendor/meals/:id', async (req, res) => {
    const token = requireVendorToken(req, res);
    if (!token) return;

    const { name, description, price, calories, protein, carbs, fats } = req.body;

    try {
        const backendRes = await backendFetch(token, `/vendor/meals/${req.params.id}`, {
            method: 'PUT',
            body: JSON.stringify({ name, description, price, calories, protein, carbs, fats }),
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="account-update-card">
        <h2>Edit menu item</h2>
        ${renderMealForm({ action: `/vendor/meals/${req.params.id}`, meal: { name, description, price, calories, protein, carbs, fats }, error: data.error })}
      </div>
    </div>
  </div>`;
            return res.status(backendRes.status).send(pageShell('Edit Menu Item', body));
        }

        res.redirect('/vendor/meals');
    } catch (err) {
        res.status(502).send(pageShell('Edit Menu Item', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

router.post('/vendor/meals/:id/delete', async (req, res) => {
    const token = requireVendorToken(req, res);
    if (!token) return;

    try {
        await backendFetch(token, `/vendor/meals/${req.params.id}`, { method: 'DELETE' });
    } catch (err) {
        // Fall through — the redirect below will simply still show the item,
        // which is an honest reflection of the delete not having gone through.
    }
    res.redirect('/vendor/meals');
});

router.post('/vendor/meals/:id/toggle', async (req, res) => {
    const token = requireVendorToken(req, res);
    if (!token) return;

    try {
        const currentRes = await backendFetch(token, `/vendor/meals/${req.params.id}`);
        const current = await currentRes.json();
        if (currentRes.ok) {
            await backendFetch(token, `/vendor/meals/${req.params.id}/availability`, {
                method: 'PATCH',
                body: JSON.stringify({ is_available: !current.is_available }),
            });
        }
    } catch (err) {
        // Same as delete above — redirect regardless and let the list reflect reality.
    }
    res.redirect('/vendor/meals');
});

module.exports = router;
