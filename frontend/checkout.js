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
const CHECKOUT_STYLES = `<style>
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
  .builder-totals {
    margin-top: 24px; background: #fff8f2; border: 1px solid #f1d3b2;
    border-radius: 24px; padding: 24px;
  }
  .builder-totals .macro-grid { margin-top: 16px; }
</style>`;

router.get('/checkout', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    try {
        const backendRes = await backendFetch(token, '/cart');
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.status(backendRes.status).send(pageShell('Checkout', `<p>${escapeHtml(data.error || 'Failed to load your cart.')}</p>`));
        }

        if (!data.items.length) {
            const body = `
      <div class="auth-shell">
        <div class="auth-card auth-production-card">
          <div class="account-hero">
            <div>
              <h1>Checkout</h1>
              <p>Your cart is empty — nothing to check out yet. <a href="/">Browse the menu →</a></p>
            </div>
          </div>
        </div>
      </div>`;
            return res.send(pageShell('Checkout', body));
        }

        const itemsHtml = data.items.map((item) => `
    <div class="cart-item">
      <div class="cart-item-info">
        <h3>${item.quantity} × ${escapeHtml(item.name)}</h3>
        <div class="meal-macros">
          <span>${item.item_calories} kcal</span>
          <span>${item.item_protein}g protein</span>
          <span>${item.item_carbs}g carbs</span>
          <span>${item.item_fats}g fats</span>
        </div>
      </div>
      <div class="cart-item-price">$${item.item_price.toFixed(2)}</div>
    </div>`).join('');

        const errorMsg = req.query.error ? `<div class="auth-message error">${escapeHtml(req.query.error)}</div>` : '';

        const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="auth-nav">
        <a class="nav-link" href="/cart">Back to Cart</a>
        <a class="logout-button" href="/logout">Log Out</a>
      </div>
      ${errorMsg}
      <div class="account-hero">
        <div>
          <h1>Review &amp; Confirm</h1>
          <p>Check your order before it goes to the vendor.</p>
        </div>
      </div>
      <main>
        <div class="cart-items">${itemsHtml}</div>
        <div class="builder-totals">
          <h2>Order Total</h2>
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
          <form method="POST" action="/checkout">
            <button type="submit" class="btn-submit" style="margin-top: 20px;">Place Order</button>
          </form>
        </div>
      </main>
    </div>
  </div>`;
        res.send(pageShell('Checkout', body, CHECKOUT_STYLES));
    } catch (err) {
        res.status(502).send(pageShell('Checkout', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

router.post('/checkout', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    try {
        const backendRes = await backendFetch(token, '/checkout', { method: 'POST' });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.redirect('/checkout?error=' + encodeURIComponent(data.error || 'Could not place your order.'));
        }

        const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="account-hero">
        <div>
          <h1>Order Placed!</h1>
          <p>Order #${data.order_id} confirmed — $${data.total_price.toFixed(2)} total, logged to today's nutrition.</p>
          <p><a href="/dashboard">View your daily fitness dashboard →</a></p>
          <p><a href="/">Back to menu →</a></p>
        </div>
      </div>
    </div>
  </div>`;
        res.send(pageShell('Order Confirmed', body));
    } catch (err) {
        res.status(502).send(pageShell('Checkout', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

module.exports = router;
