const express = require('express');
const router = express.Router();
const { backendRequest } = require('../lib/backend');
const { requireLoginPage, requireLoginApi } = require('../lib/auth');
const { pageShell } = require('../views/layout');

router.get('/dashboard', requireLoginPage, (req, res) => {
    res.send(pageShell({
        title: 'Merchant Dashboard',
        activeNav: 'dashboard',
        bodyHtml: `
          <div class="dashboard-header">
            <div>
              <h1>Merchant Dashboard</h1>
              <p id="vendor-name" class="muted">Loading vendor…</p>
            </div>
            <form method="POST" action="/logout"><button type="submit" class="secondary">Log Out</button></form>
          </div>

          <section class="card">
            <h2 id="form-title">Add Menu Item</h2>
            <p id="form-error" class="error hidden"></p>
            <form id="meal-form">
              <input type="hidden" id="meal-id" value="">
              <label>Name
                <input type="text" id="meal-name" required>
              </label>
              <label>Description
                <textarea id="meal-description" rows="2"></textarea>
              </label>
              <div class="grid">
                <label>Price ($)
                  <input type="number" id="meal-price" step="0.01" min="0" required>
                </label>
                <label>Calories
                  <input type="number" id="meal-calories" min="0" step="1" required>
                </label>
                <label>Protein (g)
                  <input type="number" id="meal-protein" min="0" step="1" required>
                </label>
                <label>Carbs (g)
                  <input type="number" id="meal-carbs" min="0" step="1" required>
                </label>
                <label>Fats (g)
                  <input type="number" id="meal-fats" min="0" step="1" required>
                </label>
              </div>
              <label class="checkbox">
                <input type="checkbox" id="meal-available" checked> Available on marketplace
              </label>
              <div class="form-actions">
                <button type="submit" id="form-submit">Add Item</button>
                <button type="button" id="form-cancel" class="secondary hidden">Cancel Edit</button>
              </div>
            </form>
          </section>

          <section class="card">
            <h2>Your Menu Items</h2>
            <table class="meal-table">
              <thead>
                <tr>
                  <th>Name</th><th>Price</th><th>Cal</th><th>Protein</th><th>Carbs</th><th>Fats</th><th>Available</th><th></th>
                </tr>
              </thead>
              <tbody id="meal-rows"><tr><td colspan="8" class="muted">Loading…</td></tr></tbody>
            </table>
          </section>
        `,
        extraScripts: ['/dashboard.js'],
    }));
});

// ---- JSON proxy: browser -> Express (cookie auth) -> Flask (bearer token) ----

router.get('/api/dashboard/me', requireLoginApi, async (req, res) => {
    const { status, data } = await backendRequest('/api/vendor/me', { token: req.vendorToken });
    res.status(status).json(data);
});

router.get('/api/dashboard/meals', requireLoginApi, async (req, res) => {
    const { status, data } = await backendRequest('/api/vendor/meals', { token: req.vendorToken });
    res.status(status).json(data);
});

router.post('/api/dashboard/meals', requireLoginApi, async (req, res) => {
    const { status, data } = await backendRequest('/api/vendor/meals', {
        method: 'POST',
        token: req.vendorToken,
        body: req.body,
    });
    res.status(status).json(data);
});

router.put('/api/dashboard/meals/:mealId', requireLoginApi, async (req, res) => {
    const { status, data } = await backendRequest(`/api/vendor/meals/${req.params.mealId}`, {
        method: 'PUT',
        token: req.vendorToken,
        body: req.body,
    });
    res.status(status).json(data);
});

router.patch('/api/dashboard/meals/:mealId/availability', requireLoginApi, async (req, res) => {
    const { status, data } = await backendRequest(`/api/vendor/meals/${req.params.mealId}/availability`, {
        method: 'PATCH',
        token: req.vendorToken,
        body: req.body,
    });
    res.status(status).json(data);
});

router.delete('/api/dashboard/meals/:mealId', requireLoginApi, async (req, res) => {
    const { status, data } = await backendRequest(`/api/vendor/meals/${req.params.mealId}`, {
        method: 'DELETE',
        token: req.vendorToken,
    });
    res.status(status).json(data);
});

module.exports = router;
