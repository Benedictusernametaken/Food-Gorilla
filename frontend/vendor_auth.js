const express = require('express');
const router = express.Router();

// Set via docker-compose.yml -> resolves to the backend container over
// Docker's internal network. Never hardcode this.
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:5000';

// Separate cookie from the customer session (fg_token) so a browser can't
// mix up a vendor session with a customer session.
const VENDOR_TOKEN_COOKIE = 'fg_vendor_token';

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
}

// Decodes the JWT payload for display purposes only (e.g. showing the
// logged-in restaurant name). The signature is never checked here — any
// route that needs to trust the identity re-verifies against the backend
// instead of relying on this decode.
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

function renderVendorAuthPage({ loginError, signupError, notice } = {}) {
    const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="top-brand">
        <div class="logo-mark">
          <span class="logo-icon">🦍</span>
          <span>Food Gorilla</span>
        </div>
      </div>
      <div class="auth-brightbar">
        <span class="tag">Vendor Portal</span>
      </div>

      <div class="auth-panels">
        <div class="auth-hero">
          <div class="hero-badge">Partner With Us</div>
          <h1>Grow your restaurant on Food Gorilla</h1>
          <p>Manage your menu, tag every item with exact nutrition, and get discovered by fitness-focused customers searching by macros.</p>

          <ul class="hero-features">
            <li>Create, update, and retire menu items in one dashboard</li>
            <li>Set exact calories, protein, carbs, and fats per item</li>
            <li>Toggle availability the moment you run out of stock</li>
          </ul>
        </div>

        <div class="auth-forms">
          ${notice ? `<div class="auth-message success">${escapeHtml(notice)}</div>` : ''}
          <section class="auth-form-card">
            <h2>Register your restaurant</h2>
            <p>Create your Food Gorilla vendor account.</p>
            <form id="vendorSignupForm" method="POST" action="/vendor/signup">
              <input type="text" name="restaurant_name" placeholder="Restaurant name" required>
              <input type="text" name="cuisine_type" placeholder="Cuisine type (optional)">
              <input type="email" name="email" placeholder="Business email" required>
              <input type="password" name="password" placeholder="Password (min. 8 characters)" required minlength="8">
              <input type="password" name="passwordConfirm" placeholder="Confirm password" required minlength="8">
              <button type="submit">Create Vendor Account</button>
            </form>
            ${signupError ? `<div class="auth-message error">${escapeHtml(signupError)}</div>` : ''}
          </section>

          <section class="auth-form-card login-card">
            <h2>Vendor Log In</h2>
            <p>Welcome back — manage your menu and orders.</p>
            <form id="vendorLoginForm" method="POST" action="/vendor/login">
              <input type="email" name="email" placeholder="Business email" required>
              <input type="password" name="password" placeholder="Password" required>
              <button type="submit">Log In</button>
            </form>
            ${loginError ? `<div class="auth-message error">${escapeHtml(loginError)}</div>` : ''}
          </section>
        </div>
      </div>
    </div>
  </div>`;
    return pageShell('Vendor Log In / Register', body);
}

router.get('/vendor/login', (req, res) => {
    res.send(renderVendorAuthPage({ notice: req.query.notice }));
});

router.get('/vendor/signup', (req, res) => {
    res.redirect('/vendor/login');
});

router.post('/vendor/signup', async (req, res) => {
    const { restaurant_name, cuisine_type, email, password, passwordConfirm } = req.body;

    if (password !== passwordConfirm) {
        return res.status(400).send(renderVendorAuthPage({ signupError: 'Passwords do not match.' }));
    }

    try {
        const backendRes = await fetch(`${BACKEND_URL}/vendor/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ restaurant_name, cuisine_type, email, password }),
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.status(backendRes.status).send(renderVendorAuthPage({ signupError: data.error || 'Registration failed.' }));
        }

        res.cookie(VENDOR_TOKEN_COOKIE, data.token, { httpOnly: true, sameSite: 'lax' });
        res.redirect('/vendor/portal');
    } catch (err) {
        res.status(502).send(renderVendorAuthPage({ signupError: `Could not reach the backend: ${err.message}` }));
    }
});

router.post('/vendor/login', async (req, res) => {
    const { email, password } = req.body;

    try {
        const backendRes = await fetch(`${BACKEND_URL}/vendor/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.status(backendRes.status).send(renderVendorAuthPage({ loginError: data.error || 'Login failed.' }));
        }

        res.cookie(VENDOR_TOKEN_COOKIE, data.token, { httpOnly: true, sameSite: 'lax' });
        res.redirect('/vendor/portal');
    } catch (err) {
        res.status(502).send(renderVendorAuthPage({ loginError: `Could not reach the backend: ${err.message}` }));
    }
});

router.get('/vendor/portal', (req, res) => {
    const token = req.cookies[VENDOR_TOKEN_COOKIE];
    const payload = token && decodeTokenPayload(token);

    if (!payload) {
        return res.redirect('/vendor/login');
    }

    const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="auth-nav">
        <a class="logout-button" href="/vendor/logout">Log Out</a>
      </div>
      <div class="account-hero">
        <div>
          <h1>Welcome back, ${escapeHtml(payload.restaurant_name)}!</h1>
          <p>This is a placeholder vendor portal for Story 8 — full menu CRUD management lands with Story 5.</p>
        </div>
      </div>
    </div>
  </div>`;
    res.send(pageShell('Vendor Portal', body));
});

router.get('/vendor/logout', (req, res) => {
    res.clearCookie(VENDOR_TOKEN_COOKIE);
    res.redirect('/vendor/login?notice=' + encodeURIComponent('You have been logged out.'));
});

module.exports = router;
