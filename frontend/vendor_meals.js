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

// Page-specific styling for the ingredient picker. Kept scoped to this
// page (rather than added to the shared stylesheet) so it can't collide
// with other stories' edits to public/css/style.css.
const VENDOR_MEALS_STYLES = `<style>
  .ingredient-picker { display: grid; gap: 10px; max-height: 320px; overflow-y: auto; border: 1px solid #f0d1b8; border-radius: 12px; padding: 14px; background: #fff9f2; margin-bottom: 8px; }
  .ingredient-picker-row { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
  .ingredient-picker-row label { display: flex; align-items: center; gap: 8px; font-weight: 500; color: #4b371f; }
  .ingredient-picker-row input[type="checkbox"] { width: auto; }
  .ingredient-meta { font-size: 0.85rem; color: #7b5b42; font-weight: 400; }
  .ingredient-qty { width: 70px; }
</style>`;

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

function renderIngredientPicker(catalog, mealIngredients = []) {
    if (!catalog.length) {
        return '<p class="empty-state">No ingredients in the catalog yet — add one below first.</p>';
    }
    return catalog.map((ing) => {
        const current = mealIngredients.find((mi) => mi.ingredient_id === ing.ingredient_id);
        return `
      <div class="ingredient-picker-row">
        <label>
          <input type="checkbox" name="ingredient_${ing.ingredient_id}_enabled" value="1" ${current ? 'checked' : ''}>
          ${escapeHtml(ing.name)}
          <span class="ingredient-meta">(${ing.calories_per_unit} kcal, ${ing.protein_per_unit}g protein per ${escapeHtml(ing.unit)}, $${ing.price_per_unit.toFixed(2)})</span>
        </label>
        <input type="number" min="1" class="ingredient-qty" name="ingredient_${ing.ingredient_id}_quantity" value="${current ? current.default_quantity : 1}">
      </div>`;
    }).join('');
}

function renderMealForm({ action, meal, error, ingredientCatalog = [] } = {}) {
    const mealIngredients = meal?.ingredients || [];
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
            <div class="form-group">
              <label>Customizable Ingredients (optional — customers can adjust quantities when ordering)</label>
              <div class="ingredient-picker">${renderIngredientPicker(ingredientCatalog, mealIngredients)}</div>
            </div>
            <button type="submit" class="btn-submit">${meal ? 'Save Changes' : 'Add Menu Item'}</button>
          </form>
          ${error ? `<div class="auth-message error">${escapeHtml(error)}</div>` : ''}`;
}

function renderAddIngredientForm(redirectTo, error) {
    return `
      <div class="account-update-card" style="margin-top: 20px;">
        <h3>Add a New Ingredient</h3>
        <p class="empty-state">Adds to the shared ingredient catalog every vendor can use.</p>
        <form method="POST" action="/vendor/ingredients">
          <input type="hidden" name="redirect_to" value="${escapeHtml(redirectTo)}">
          <div class="form-group">
            <label>Name</label>
            <input type="text" name="name" required>
          </div>
          <div class="form-group">
            <label>Unit (e.g. "50g", "1 scoop")</label>
            <input type="text" name="unit" placeholder="grams">
          </div>
          <div class="form-group">
            <label>Calories / unit</label>
            <input type="number" min="0" name="calories_per_unit" required>
          </div>
          <div class="form-group">
            <label>Protein (g) / unit</label>
            <input type="number" min="0" name="protein_per_unit" required>
          </div>
          <div class="form-group">
            <label>Carbs (g) / unit</label>
            <input type="number" min="0" name="carbs_per_unit" required>
          </div>
          <div class="form-group">
            <label>Fats (g) / unit</label>
            <input type="number" min="0" name="fats_per_unit" required>
          </div>
          <div class="form-group">
            <label>Price ($) / unit</label>
            <input type="number" step="0.01" min="0" name="price_per_unit" required>
          </div>
          <button type="submit" class="btn-submit">Add Ingredient</button>
        </form>
        ${error ? `<div class="auth-message error">${escapeHtml(error)}</div>` : ''}
      </div>`;
}

async function loadIngredientCatalog(token) {
    const res = await backendFetch(token, '/vendor/ingredients');
    if (!res.ok) return [];
    const data = await res.json();
    return data.ingredients || [];
}

function collectIngredientSelection(catalog, body) {
    const ingredients = {};
    for (const ing of catalog) {
        if (body[`ingredient_${ing.ingredient_id}_enabled`]) {
            const qty = parseInt(body[`ingredient_${ing.ingredient_id}_quantity`], 10);
            ingredients[ing.ingredient_id] = Number.isFinite(qty) && qty > 0 ? qty : 1;
        }
    }
    return ingredients;
}

router.get('/vendor/meals', async (req, res) => {
    const token = requireVendorToken(req, res);
    if (!token) return;

    try {
        const [backendRes, ingredientCatalog] = await Promise.all([
            backendFetch(token, '/vendor/meals'),
            loadIngredientCatalog(token),
        ]);
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
        ${renderMealForm({ action: '/vendor/meals', ingredientCatalog })}
      </div>
      ${renderAddIngredientForm('/vendor/meals', req.query.ingredientError)}
    </div>
  </div>`;
        res.send(pageShell('Menu Management', body, VENDOR_MEALS_STYLES));
    } catch (err) {
        res.status(502).send(pageShell('Menu Management', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

router.post('/vendor/meals', async (req, res) => {
    const token = requireVendorToken(req, res);
    if (!token) return;

    const { name, description, price, calories, protein, carbs, fats } = req.body;

    try {
        const ingredientCatalog = await loadIngredientCatalog(token);
        const ingredients = collectIngredientSelection(ingredientCatalog, req.body);

        const backendRes = await backendFetch(token, '/vendor/meals', {
            method: 'POST',
            body: JSON.stringify({ name, description, price, calories, protein, carbs, fats, ingredients }),
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            const meal = {
                name, description, price, calories, protein, carbs, fats,
                ingredients: Object.entries(ingredients).map(([id, qty]) => ({ ingredient_id: Number(id), default_quantity: qty })),
            };
            const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="account-update-card">
        <h2>Add a menu item</h2>
        ${renderMealForm({ action: '/vendor/meals', meal, error: data.error, ingredientCatalog })}
      </div>
    </div>
  </div>`;
            return res.status(backendRes.status).send(pageShell('Menu Management', body, VENDOR_MEALS_STYLES));
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
        const [backendRes, ingredientCatalog] = await Promise.all([
            backendFetch(token, `/vendor/meals/${req.params.id}`),
            loadIngredientCatalog(token),
        ]);
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
        ${renderMealForm({ action: `/vendor/meals/${data.meal_id}`, meal: data, ingredientCatalog })}
      </div>
      ${renderAddIngredientForm(`/vendor/meals/${data.meal_id}/edit`, req.query.ingredientError)}
    </div>
  </div>`;
        res.send(pageShell('Edit Menu Item', body, VENDOR_MEALS_STYLES));
    } catch (err) {
        res.status(502).send(pageShell('Edit Menu Item', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

router.post('/vendor/meals/:id', async (req, res) => {
    const token = requireVendorToken(req, res);
    if (!token) return;

    const { name, description, price, calories, protein, carbs, fats } = req.body;

    try {
        const ingredientCatalog = await loadIngredientCatalog(token);
        const ingredients = collectIngredientSelection(ingredientCatalog, req.body);

        const backendRes = await backendFetch(token, `/vendor/meals/${req.params.id}`, {
            method: 'PUT',
            body: JSON.stringify({ name, description, price, calories, protein, carbs, fats, ingredients }),
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            const meal = {
                name, description, price, calories, protein, carbs, fats,
                ingredients: Object.entries(ingredients).map(([id, qty]) => ({ ingredient_id: Number(id), default_quantity: qty })),
            };
            const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="account-update-card">
        <h2>Edit menu item</h2>
        ${renderMealForm({ action: `/vendor/meals/${req.params.id}`, meal, error: data.error, ingredientCatalog })}
      </div>
    </div>
  </div>`;
            return res.status(backendRes.status).send(pageShell('Edit Menu Item', body, VENDOR_MEALS_STYLES));
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
        console.error(err);
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
        console.error(err);
        // Same as delete above — redirect regardless and let the list reflect reality.
    }
    res.redirect('/vendor/meals');
});

router.post('/vendor/ingredients', async (req, res) => {
    const token = requireVendorToken(req, res);
    if (!token) return;

    const { name, unit, calories_per_unit, protein_per_unit, carbs_per_unit, fats_per_unit, price_per_unit, redirect_to } = req.body;
    // Only ever redirect back into this same feature's own pages.
    const target = typeof redirect_to === 'string' && redirect_to.startsWith('/vendor/') ? redirect_to : '/vendor/meals';

    try {
        const backendRes = await backendFetch(token, '/vendor/ingredients', {
            method: 'POST',
            body: JSON.stringify({ name, unit, calories_per_unit, protein_per_unit, carbs_per_unit, fats_per_unit, price_per_unit }),
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.redirect(`${target}?ingredientError=${encodeURIComponent(data.error || 'Could not add ingredient.')}`);
        }

        res.redirect(target);
    } catch (err) {
        res.status(502).send(pageShell('Menu Management', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

module.exports = router;
