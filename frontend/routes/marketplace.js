const express = require('express');
const router = express.Router();
const { backendRequest } = require('../lib/backend');
const { pageShell } = require('../views/layout');

router.get('/', (req, res) => {
    res.send(pageShell({
        title: 'Marketplace',
        activeNav: 'marketplace',
        bodyHtml: `
          <h1>Find Your Next Meal</h1>
          <form id="search-form" class="search-form">
            <input type="search" id="search-q" placeholder="Search meals by name…">
            <div class="grid">
              <label>Max Calories
                <input type="number" id="max-calories" min="0">
              </label>
              <label>Min Protein (g)
                <input type="number" id="min-protein" min="0">
              </label>
              <label>Max Price ($)
                <input type="number" id="max-price" min="0" step="0.01">
              </label>
            </div>
            <button type="submit">Search</button>
          </form>
          <div id="results" class="meal-grid"><p class="muted">Loading meals…</p></div>
        `,
        extraScripts: ['/marketplace.js'],
    }));
});

router.get('/api/marketplace/search', async (req, res) => {
    const query = new URLSearchParams(req.query).toString();
    const { status, data } = await backendRequest(`/api/meals/search${query ? `?${query}` : ''}`);
    res.status(status).json(data);
});

module.exports = router;
