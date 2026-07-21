const express = require('express');
const router = express.Router();

// Set via docker-compose.yml -> resolves to the backend container over
// Docker's internal network. Never hardcode this.
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:5000';

// Same cookie Story 7's auth.js sets on login/signup.
const TOKEN_COOKIE = 'fg_token';

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
}

// Decodes the JWT payload for display purposes only (e.g. showing the
// logged-in username in the nav). The signature is never checked here —
// any route that needs to trust the identity re-verifies against the
// backend instead of relying on this decode.
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

// Page-specific styling for the slider filter panel and meal cards. Kept
// scoped to this page (rather than added to the shared stylesheet) so it
// can't collide with other stories' edits to public/css/style.css.
const MENU_STYLES = `<style>
  .menu-page { max-width: 1100px; margin: 0 auto; padding: 40px 24px; }
  .filter-panel {
    background: #fff8f2; border: 1px solid #f1d3b2; border-radius: 24px;
    padding: 24px; margin-bottom: 32px; display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px;
  }
  .filter-field label { display: flex; justify-content: space-between; font-weight: 600; color: #5b432e; margin-bottom: 8px; }
  .filter-field input[type="range"] { width: 100%; }
  .restaurant-group { margin-bottom: 36px; }
  .restaurant-group h2 { color: #4b371f; margin-bottom: 16px; }
  .meal-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 18px; }
  .meal-card {
    border: 1px solid #f3ceb3; background: #fff4ea; border-radius: 18px;
    padding: 18px 20px; transition: opacity 0.15s ease;
  }
  .meal-card.hidden { display: none; }
  .meal-card h3 { color: #4b371f; margin-bottom: 6px; }
  .meal-card .meal-price { font-weight: 700; color: #a95c24; margin-bottom: 8px; }
  .meal-card .meal-desc { color: #7b5b42; font-size: 0.92rem; margin-bottom: 12px; }
  .meal-macros { display: flex; flex-wrap: wrap; gap: 8px; }
  .meal-macros span {
    background: #f56a28; color: white; border-radius: 999px; padding: 4px 10px;
    font-size: 0.85rem; font-weight: 600;
  }
  .menu-top-links { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; margin: 16px 0 24px; }
</style>`;

function computeBounds(meals, key) {
    if (meals.length === 0) return { min: 0, max: 100 };
    const values = meals.map((m) => m[key]);
    const min = Math.min(...values);
    const max = Math.max(...values, 0);
    // A single meal (or several tied on this macro) would otherwise produce
    // min === max, which renders as a range input with no draggable travel.
    if (min === max) return { min: Math.max(0, min - 10), max: max + 10 };
    return { min, max };
}

function renderSlider({ id, label, min, max, isMin }) {
    const defaultValue = isMin ? min : max;
    return `
      <div class="filter-field">
        <label for="${id}">${label} <span id="${id}-value">${defaultValue}</span></label>
        <input type="range" id="${id}" min="${min}" max="${max}" value="${defaultValue}" data-macro="${id}">
      </div>`;
}

function renderMealCard(meal) {
    return `
    <div class="meal-card"
         data-meal-id="${meal.meal_id}"
         data-calories="${meal.calories}"
         data-protein="${meal.protein}"
         data-carbs="${meal.carbs}"
         data-fats="${meal.fats}">
      <h3>${escapeHtml(meal.name)}</h3>
      <div class="meal-price">$${meal.price.toFixed(2)}</div>
      ${meal.description ? `<div class="meal-desc">${escapeHtml(meal.description)}</div>` : ''}
      <div class="meal-macros">
        <span>${meal.calories} kcal</span>
        <span>${meal.protein}g protein</span>
        <span>${meal.carbs}g carbs</span>
        <span>${meal.fats}g fats</span>
      </div>
      <div style="margin-top: 12px;"><a class="nav-link" href="/meals/${meal.meal_id}/customize">Customize this meal →</a></div>
    </div>`;
}

router.get('/', async (req, res) => {
    const token = req.cookies[TOKEN_COOKIE];
    const payload = token && decodeTokenPayload(token);

    try {
        // Server-side call: this happens inside the Docker network, never in
        // the user's browser, so no CORS setup is needed.
        const backendRes = await fetch(`${BACKEND_URL}/menu`);
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.status(backendRes.status).send(pageShell('Food Gorilla', `<p>${escapeHtml(data.error || 'Failed to load the menu.')}</p>`));
        }

        const meals = data.meals;

        const caloriesBounds = computeBounds(meals, 'calories');
        const proteinBounds = computeBounds(meals, 'protein');
        const carbsBounds = computeBounds(meals, 'carbs');
        const fatsBounds = computeBounds(meals, 'fats');

        const groups = new Map();
        for (const meal of meals) {
            if (!groups.has(meal.restaurant_name)) groups.set(meal.restaurant_name, []);
            groups.get(meal.restaurant_name).push(meal);
        }

        const groupsHtml = meals.length
            ? [...groups.entries()].map(([restaurantName, restaurantMeals]) => `
      <div class="restaurant-group">
        <h2>${escapeHtml(restaurantName)}</h2>
        <div class="meal-grid">
          ${restaurantMeals.map(renderMealCard).join('')}
        </div>
      </div>`).join('')
            : '<p class="empty-state">No meals available right now — check back soon.</p>';

        const body = `
  <div class="menu-page">
    <div class="top-brand">
      <div class="logo-mark">
        <span class="logo-icon">🦍</span>
        <span>Food Gorilla</span>
      </div>
    </div>
    <div class="menu-top-links">
      ${payload
          ? `<a class="nav-link" href="/profile">${escapeHtml(payload.username)}'s Profile</a>
      <a class="nav-link" href="/logout">Log Out</a>`
          : `<a class="nav-link" href="/login">Log In</a>`}
      <a class="nav-link" href="/cart">Your Cart</a>
      <a class="nav-link" href="/vendor/login">Vendor Portal</a>
    </div>
    <h1>Find meals that fit your macros</h1>

    <div class="filter-panel">
      ${renderSlider({ id: 'calories', label: 'Max Calories', min: caloriesBounds.min, max: caloriesBounds.max, isMin: false })}
      ${renderSlider({ id: 'protein', label: 'Min Protein (g)', min: proteinBounds.min, max: proteinBounds.max, isMin: true })}
      ${renderSlider({ id: 'carbs', label: 'Max Carbs (g)', min: carbsBounds.min, max: carbsBounds.max, isMin: false })}
      ${renderSlider({ id: 'fats', label: 'Max Fats (g)', min: fatsBounds.min, max: fatsBounds.max, isMin: false })}
    </div>

    <div id="menuResults">
      ${groupsHtml}
    </div>
    <p id="noResults" class="empty-state" style="display:none">No meals match your current filters.</p>
  </div>

  <script>
    (function () {
      const sliders = {
        calories: { el: document.getElementById('calories'), mode: 'max' },
        protein: { el: document.getElementById('protein'), mode: 'min' },
        carbs: { el: document.getElementById('carbs'), mode: 'max' },
        fats: { el: document.getElementById('fats'), mode: 'max' },
      };
      const cards = Array.from(document.querySelectorAll('.meal-card'));
      const groupEls = Array.from(document.querySelectorAll('.restaurant-group'));
      const noResults = document.getElementById('noResults');

      function applyFilters() {
        let visibleCount = 0;
        for (const card of cards) {
          let matches = true;
          for (const key of Object.keys(sliders)) {
            const { el, mode } = sliders[key];
            const sliderValue = Number(el.value);
            const cardValue = Number(card.dataset[key]);
            if (mode === 'max' && cardValue > sliderValue) matches = false;
            if (mode === 'min' && cardValue < sliderValue) matches = false;
          }
          card.classList.toggle('hidden', !matches);
          if (matches) visibleCount += 1;
        }
        for (const group of groupEls) {
          const hasVisible = group.querySelectorAll('.meal-card:not(.hidden)').length > 0;
          group.classList.toggle('hidden', !hasVisible);
        }
        noResults.style.display = visibleCount === 0 ? 'block' : 'none';
      }

      for (const key of Object.keys(sliders)) {
        const { el } = sliders[key];
        el.addEventListener('input', () => {
          document.getElementById(key + '-value').textContent = el.value;
          applyFilters();
        });
      }

      applyFilters();
    })();
  </script>`;

        res.send(pageShell('Food Gorilla — Menu', body, MENU_STYLES));
    } catch (err) {
        res.status(502).send(pageShell('Food Gorilla', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

module.exports = router;
