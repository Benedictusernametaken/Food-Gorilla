const express = require('express');
const router = express.Router();

// Set via docker-compose.yml -> resolves to the backend container over
// Docker's internal network. Never hardcode this.
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:5000';

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
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

// Page-specific styling, kept scoped to this page (rather than added to
// the shared stylesheet) so it can't collide with other stories' edits to
// public/css/style.css.
const BUILDER_STYLES = `<style>
  .builder-page { max-width: 720px; margin: 0 auto; padding: 40px 24px; }
  .ingredient-row {
    display: flex; align-items: center; justify-content: space-between; gap: 16px;
    border: 1px solid #f3ceb3; background: #fff4ea; border-radius: 16px;
    padding: 14px 18px; margin-bottom: 12px;
  }
  .ingredient-row .ingredient-info { display: grid; gap: 4px; }
  .ingredient-row .ingredient-name { font-weight: 700; color: #4b371f; }
  .ingredient-row .ingredient-meta { font-size: 0.85rem; color: #7b5b42; }
  .qty-control { display: flex; align-items: center; gap: 10px; }
  .qty-control button {
    width: 32px; height: 32px; border-radius: 999px; border: none;
    background: #f56a28; color: white; font-weight: 700; font-size: 1.1rem; cursor: pointer;
  }
  .qty-control button:hover { filter: brightness(1.05); }
  .qty-control .qty-value { min-width: 24px; text-align: center; font-weight: 700; }
  .builder-totals {
    margin-top: 24px; background: #fff8f2; border: 1px solid #f1d3b2;
    border-radius: 24px; padding: 24px;
  }
  .builder-totals .macro-grid { margin-top: 16px; }
  #cartConfirmation { margin-top: 20px; }
</style>`;

router.get('/meals/:id/customize', async (req, res) => {
    try {
        // Server-side call: this happens inside the Docker network, never in
        // the user's browser, so no CORS setup is needed.
        const backendRes = await fetch(`${BACKEND_URL}/meals/${req.params.id}/customize`);
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.status(backendRes.status).send(pageShell('Customize Meal', `<p>${escapeHtml(data.error || 'Meal not found.')}</p>`));
        }

        const ingredientRowsHtml = data.ingredients.length
            ? data.ingredients.map((ing) => `
      <div class="ingredient-row"
           data-ingredient-id="${ing.ingredient_id}"
           data-default-quantity="${ing.default_quantity}"
           data-price-per-unit="${ing.price_per_unit}"
           data-calories-per-unit="${ing.calories_per_unit}"
           data-protein-per-unit="${ing.protein_per_unit}"
           data-carbs-per-unit="${ing.carbs_per_unit}"
           data-fats-per-unit="${ing.fats_per_unit}">
        <div class="ingredient-info">
          <div class="ingredient-name">${escapeHtml(ing.name)}</div>
          <div class="ingredient-meta">${ing.unit} · $${ing.price_per_unit.toFixed(2)} each · ${ing.calories_per_unit} kcal each</div>
        </div>
        <div class="qty-control">
          <button type="button" class="qty-minus">−</button>
          <span class="qty-value">${ing.default_quantity}</span>
          <button type="button" class="qty-plus">+</button>
        </div>
      </div>`).join('')
            : '<p class="empty-state">This meal has no customizable ingredients.</p>';

        const body = `
  <div class="builder-page">
    <div class="page-nav"><a class="nav-link" href="/">← Back to menu</a></div>
    <h1>${escapeHtml(data.name)}</h1>
    ${data.description ? `<p>${escapeHtml(data.description)}</p>` : ''}

    <h2 class="section-label">Customize Ingredients</h2>
    <div id="ingredientList">${ingredientRowsHtml}</div>

    <div class="builder-totals">
      <h2>Your Total</h2>
      <div class="macro-grid">
        <div class="macro-card">
          <h3>Price</h3>
          <div class="macro-value">$<span id="totalPrice">${data.base_price.toFixed(2)}</span></div>
        </div>
        <div class="macro-card">
          <h3>Calories</h3>
          <div class="macro-value" id="totalCalories">${data.base_calories}</div>
          <div class="macro-unit">kcal</div>
        </div>
        <div class="macro-card">
          <h3>Protein</h3>
          <div class="macro-value" id="totalProtein">${data.base_protein}</div>
          <div class="macro-unit">grams</div>
        </div>
        <div class="macro-card">
          <h3>Carbs</h3>
          <div class="macro-value" id="totalCarbs">${data.base_carbs}</div>
          <div class="macro-unit">grams</div>
        </div>
        <div class="macro-card">
          <h3>Fats</h3>
          <div class="macro-value" id="totalFats">${data.base_fats}</div>
          <div class="macro-unit">grams</div>
        </div>
      </div>
      <button type="button" id="addToCartBtn" class="btn-submit" style="margin-top: 20px;">Add to Cart</button>
      <div id="cartConfirmation"></div>
    </div>
  </div>

  <script>
    (function () {
      const mealId = ${JSON.stringify(data.meal_id)};
      const basePrice = ${data.base_price};
      const baseCalories = ${data.base_calories};
      const baseProtein = ${data.base_protein};
      const baseCarbs = ${data.base_carbs};
      const baseFats = ${data.base_fats};
      const rows = Array.from(document.querySelectorAll('.ingredient-row'));

      function currentQuantity(row) {
        return Number(row.querySelector('.qty-value').textContent);
      }

      function recalculate() {
        let price = basePrice, calories = baseCalories, protein = baseProtein, carbs = baseCarbs, fats = baseFats;
        for (const row of rows) {
          const defaultQty = Number(row.dataset.defaultQuantity);
          const qty = currentQuantity(row);
          const delta = qty - defaultQty;
          price += delta * Number(row.dataset.pricePerUnit);
          calories += delta * Number(row.dataset.caloriesPerUnit);
          protein += delta * Number(row.dataset.proteinPerUnit);
          carbs += delta * Number(row.dataset.carbsPerUnit);
          fats += delta * Number(row.dataset.fatsPerUnit);
        }
        document.getElementById('totalPrice').textContent = Math.max(price, 0).toFixed(2);
        document.getElementById('totalCalories').textContent = Math.round(Math.max(calories, 0));
        document.getElementById('totalProtein').textContent = Math.round(Math.max(protein, 0));
        document.getElementById('totalCarbs').textContent = Math.round(Math.max(carbs, 0));
        document.getElementById('totalFats').textContent = Math.round(Math.max(fats, 0));
      }

      for (const row of rows) {
        const valueEl = row.querySelector('.qty-value');
        row.querySelector('.qty-plus').addEventListener('click', () => {
          valueEl.textContent = String(currentQuantity(row) + 1);
          recalculate();
        });
        row.querySelector('.qty-minus').addEventListener('click', () => {
          valueEl.textContent = String(Math.max(currentQuantity(row) - 1, 0));
          recalculate();
        });
      }

      document.getElementById('addToCartBtn').addEventListener('click', async () => {
        const ingredients = {};
        for (const row of rows) {
          ingredients[row.dataset.ingredientId] = currentQuantity(row);
        }

        const confirmationEl = document.getElementById('cartConfirmation');
        try {
          const res = await fetch('/cart/items', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ meal_id: mealId, ingredients }),
          });
          const data = await res.json();
          if (res.status === 401) {
            confirmationEl.innerHTML = '<div class="auth-message error">Please <a href="/login">log in</a> to add items to your cart.</div>';
            return;
          }
          if (!res.ok) {
            confirmationEl.innerHTML = '<div class="auth-message error">' + (data.error || 'Could not add this item to your cart.') + '</div>';
            return;
          }
          confirmationEl.innerHTML = '<div class="auth-message success">Added to cart — <a href="/cart">view your cart →</a></div>';
        } catch (err) {
          confirmationEl.innerHTML = '<div class="auth-message error">Could not reach the backend: ' + err.message + '</div>';
        }
      });
    })();
  </script>`;

        res.send(pageShell(`Customize ${data.name}`, body, BUILDER_STYLES));
    } catch (err) {
        res.status(502).send(pageShell('Customize Meal', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

module.exports = router;
