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

// Page-specific styling, kept scoped to this page (rather than added to
// the shared stylesheet) so it can't collide with other stories' edits to
// public/css/style.css.
const CART_STYLES = `<style>
  .cart-items { display: grid; gap: 14px; margin-top: 10px; }
  .cart-item {
    display: flex; align-items: center; justify-content: space-between; gap: 16px;
    border: 1px solid #f3ceb3; background: #fff4ea; border-radius: 16px;
    padding: 14px 20px; flex-wrap: wrap;
  }
  .cart-item-info h3 { color: #4b371f; margin-bottom: 6px; }
  .cart-item-price { font-weight: 700; color: #a95c24; min-width: 70px; text-align: right; }
  .meal-macros { display: flex; flex-wrap: wrap; gap: 8px; }
  .meal-macros span {
    background: #f56a28; color: white; border-radius: 999px; padding: 4px 10px;
    font-size: 0.85rem; font-weight: 600;
  }
  .cart-qty-form { display: flex; align-items: center; gap: 8px; }
  .cart-qty-form input[type="number"] {
    width: 60px; padding: 8px; border-radius: 10px; border: 1px solid #e4c6a2; text-align: center;
  }
  .cart-qty-form .btn-submit, .cart-item form .link-button { padding: 8px 14px; font-size: 0.85rem; }
  .builder-totals {
    margin-top: 24px; background: #fff8f2; border: 1px solid #f1d3b2;
    border-radius: 24px; padding: 24px;
  }
  .builder-totals .macro-grid { margin-top: 16px; }
  .cart-actions {
    display: flex; align-items: center; justify-content: space-between;
    gap: 16px; margin-top: 20px; flex-wrap: wrap;
  }
</style>`;

function renderCartItem(item) {
    return `
    <div class="cart-item">
      <div class="cart-item-info">
        <h3>${escapeHtml(item.name)}</h3>
        <div class="meal-macros">
          <span>${item.item_calories} kcal</span>
          <span>${item.item_protein}g protein</span>
          <span>${item.item_carbs}g carbs</span>
          <span>${item.item_fats}g fats</span>
        </div>
      </div>
      <form method="POST" action="/cart/items/${item.order_item_id}/update" class="cart-qty-form">
        <input type="number" name="quantity" value="${item.quantity}" min="1" required>
        <button type="submit" class="btn-submit">Update</button>
      </form>
      <div class="cart-item-price">$${item.item_price.toFixed(2)}</div>
      <form method="POST" action="/cart/items/${item.order_item_id}/remove">
        <button type="submit" class="link-button">Remove</button>
      </form>
    </div>`;
}

router.get('/cart', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    try {
        const backendRes = await backendFetch(token, '/cart');
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.status(backendRes.status).send(pageShell('Cart', `<p>${escapeHtml(data.error || 'Failed to load your cart.')}</p>`));
        }

        const nav = `
      <div class="auth-nav">
        <a class="nav-link" href="/">Back to Menu</a>
        <a class="logout-button" href="/logout">Log Out</a>
      </div>`;

        const errorMsg = req.query.error ? `<div class="auth-message error">${escapeHtml(req.query.error)}</div>` : '';

        let main;
        if (!data.items.length) {
            main = `
      <div class="account-hero">
        <div>
          <h1>Your Cart</h1>
          <p>Your cart is empty.</p>
          <div class="hero-actions">
            <a href="/">Browse the menu →</a>
          </div>
        </div>
      </div>`;
        } else {
            const itemsHtml = data.items.map(renderCartItem).join('');
            main = `
      <div class="account-hero">
        <div>
          <h1>Your Cart</h1>
          <p>Review your items before checking out.</p>
        </div>
      </div>
      <main>
        <div class="cart-items">${itemsHtml}</div>
        <div class="builder-totals">
          <h2>Cart Total</h2>
          <div class="macro-grid">
            <div class="macro-card">
              <h3>Price</h3>
              <div class="macro-value">$${data.total_price.toFixed(2)}</div>
            </div>
            <div class="macro-card">
              <h3>Calories</h3>
              <div class="macro-value">${data.total_calories}</div>
              <div class="macro-unit">kcal</div>
            </div>
            <div class="macro-card">
              <h3>Protein</h3>
              <div class="macro-value">${data.total_protein}</div>
              <div class="macro-unit">grams</div>
            </div>
            <div class="macro-card">
              <h3>Carbs</h3>
              <div class="macro-value">${data.total_carbs}</div>
              <div class="macro-unit">grams</div>
            </div>
            <div class="macro-card">
              <h3>Fats</h3>
              <div class="macro-value">${data.total_fats}</div>
              <div class="macro-unit">grams</div>
            </div>
          </div>
          <div class="cart-actions">
            <form method="POST" action="/cart/clear"><button type="submit" class="link-button">Clear Cart</button></form>
            <a class="btn-submit" href="/checkout">Proceed to Checkout →</a>
          </div>
        </div>
      </main>`;
        }

        const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      ${nav}
      ${errorMsg}
      ${main}
    </div>
  </div>`;
        res.send(pageShell('Your Cart', body, CART_STYLES));
    } catch (err) {
        res.status(502).send(pageShell('Your Cart', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

// Used by meal_builder.js's "Add to Cart" button (client-side fetch, JSON
// in and out) — this is the only cart route meant to be called from the
// browser rather than via a plain form POST, since it needs to report
// success/failure back into the customize page without a full reload.
router.post('/cart/items', async (req, res) => {
    const token = req.cookies[TOKEN_COOKIE];
    if (!token) {
        return res.status(401).json({ error: 'authentication required' });
    }

    try {
        const backendRes = await backendFetch(token, '/cart/items', {
            method: 'POST',
            body: JSON.stringify({
                meal_id: req.body.meal_id,
                quantity: req.body.quantity,
                ingredients: req.body.ingredients || {},
            }),
        });
        const data = await backendRes.json();
        res.status(backendRes.status).json(data);
    } catch (err) {
        res.status(502).json({ error: `Could not reach the backend: ${err.message}` });
    }
});

router.post('/cart/items/:id/update', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    const quantity = parseInt(req.body.quantity, 10);
    try {
        const backendRes = await backendFetch(token, `/cart/items/${req.params.id}`, {
            method: 'PUT',
            body: JSON.stringify({ quantity }),
        });
        const data = await backendRes.json();
        if (!backendRes.ok) {
            return res.redirect('/cart?error=' + encodeURIComponent(data.error || 'Could not update item.'));
        }
        res.redirect('/cart');
    } catch (err) {
        res.redirect('/cart?error=' + encodeURIComponent(`Could not reach the backend: ${err.message}`));
    }
});

router.post('/cart/items/:id/remove', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    try {
        const backendRes = await backendFetch(token, `/cart/items/${req.params.id}`, { method: 'DELETE' });
        const data = await backendRes.json();
        if (!backendRes.ok) {
            return res.redirect('/cart?error=' + encodeURIComponent(data.error || 'Could not remove item.'));
        }
        res.redirect('/cart');
    } catch (err) {
        res.redirect('/cart?error=' + encodeURIComponent(`Could not reach the backend: ${err.message}`));
    }
});

router.post('/cart/clear', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    try {
        await backendFetch(token, '/cart', { method: 'DELETE' });
        res.redirect('/cart');
    } catch (err) {
        res.redirect('/cart?error=' + encodeURIComponent(`Could not reach the backend: ${err.message}`));
    }
});

module.exports = router;
