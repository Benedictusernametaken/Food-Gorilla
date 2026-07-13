const express = require('express');
const router = express.Router();

// Set via docker-compose.yml -> resolves to the backend container over
// Docker's internal network. Never hardcode this.
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:5000';

const TOKEN_COOKIE = 'fg_token';

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
}

// Decodes the JWT payload for display purposes only (e.g. showing the
// logged-in username). The signature is never checked here — any route
// that needs to trust the identity re-verifies against the backend
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

function renderAuthPage({ loginError, signupError, notice } = {}) {
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
        <span class="tag">Macro-Tracking Food Delivery</span>
      </div>

      <div class="auth-panels">
        <div class="auth-hero">
          <div class="hero-badge">Eat On Target</div>
          <h1>Welcome to Food Gorilla</h1>
          <p>Order meals that fit your daily calories and macros — every menu item is tagged with exact nutrition so hitting your targets is effortless.</p>

          <ul class="hero-features">
            <li>Filter menus by calories, protein, carbs, and fats</li>
            <li>Build your own macro profile and daily targets</li>
            <li>Track every order against your daily nutrition goals</li>
          </ul>
        </div>

        <div class="auth-forms">
          ${notice ? `<div class="auth-message success">${escapeHtml(notice)}</div>` : ''}
          <section class="auth-form-card">
            <h2>Sign Up</h2>
            <p>Create your Food Gorilla account.</p>
            <form id="signupForm" method="POST" action="/signup">
              <input type="text" name="username" placeholder="Username" required>
              <input type="email" name="email" placeholder="Email" required>
              <input type="password" name="password" placeholder="Password (min. 8 characters)" required minlength="8">
              <input type="password" name="passwordConfirm" placeholder="Confirm password" required minlength="8">
              <button type="submit">Create Account</button>
            </form>
            ${signupError ? `<div class="auth-message error">${escapeHtml(signupError)}</div>` : ''}
          </section>

          <section class="auth-form-card login-card">
            <h2>Log In</h2>
            <p>Welcome back — pick up where you left off.</p>
            <form id="loginForm" method="POST" action="/login">
              <input type="text" name="identifier" placeholder="Email or username" required>
              <input type="password" name="password" placeholder="Password" required>
              <button type="submit">Log In</button>
            </form>
            ${loginError ? `<div class="auth-message error">${escapeHtml(loginError)}</div>` : ''}
            <p style="margin-top: 12px; font-size: 0.95rem; color: #555;">
              Forgot your password? <a href="/reset-request">Reset it here</a>.
            </p>
          </section>
        </div>
      </div>
    </div>
  </div>`;
    return pageShell('Log In / Sign Up', body);
}

function renderResetRequestPage({ error, message, resetLink } = {}) {
    const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="top-brand">
        <div class="logo-mark">
          <span class="logo-icon">🦍</span>
          <span>Food Gorilla</span>
        </div>
      </div>
      <div class="auth-forms">
        <section class="auth-form-card">
          <h2>Reset your password</h2>
          <p>Enter the email on your account and we'll send you a reset link.</p>
          <form method="POST" action="/reset-request">
            <input type="email" name="email" placeholder="Email" required>
            <button type="submit">Send Reset Link</button>
          </form>
          ${error ? `<div class="auth-message error">${escapeHtml(error)}</div>` : ''}
          ${message ? `<div class="auth-message success">${escapeHtml(message)}</div>` : ''}
          ${resetLink ? `<div class="auth-message success">No email service is configured yet, so here's your reset link directly: <a href="${resetLink}">${resetLink}</a></div>` : ''}
          <p style="margin-top: 12px; font-size: 0.95rem; color: #555;">
            <a href="/login">Back to login</a>
          </p>
        </section>
      </div>
    </div>
  </div>`;
    return pageShell('Reset Password', body);
}

function renderResetConfirmPage({ token, error }) {
    const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="top-brand">
        <div class="logo-mark">
          <span class="logo-icon">🦍</span>
          <span>Food Gorilla</span>
        </div>
      </div>
      <div class="auth-forms">
        <section class="auth-form-card">
          <h2>Choose a new password</h2>
          <form method="POST" action="/reset-confirm">
            <input type="hidden" name="token" value="${escapeHtml(token)}">
            <input type="password" name="new_password" placeholder="New password (min. 8 characters)" required minlength="8">
            <button type="submit">Update Password</button>
          </form>
          ${error ? `<div class="auth-message error">${escapeHtml(error)}</div>` : ''}
        </section>
      </div>
    </div>
  </div>`;
    return pageShell('Choose New Password', body);
}

router.get('/login', (req, res) => {
    res.send(renderAuthPage({ notice: req.query.notice }));
});

router.get('/signup', (req, res) => {
    res.redirect('/login');
});

router.post('/signup', async (req, res) => {
    const { username, email, password, passwordConfirm } = req.body;

    if (password !== passwordConfirm) {
        return res.status(400).send(renderAuthPage({ signupError: 'Passwords do not match.' }));
    }

    try {
        const backendRes = await fetch(`${BACKEND_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password }),
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.status(backendRes.status).send(renderAuthPage({ signupError: data.error || 'Registration failed.' }));
        }

        res.cookie(TOKEN_COOKIE, data.token, { httpOnly: true, sameSite: 'lax' });
        res.redirect('/profile');
    } catch (err) {
        res.status(502).send(renderAuthPage({ signupError: `Could not reach the backend: ${err.message}` }));
    }
});

router.post('/login', async (req, res) => {
    const { identifier, password } = req.body;

    try {
        const backendRes = await fetch(`${BACKEND_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ identifier, password }),
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.status(backendRes.status).send(renderAuthPage({ loginError: data.error || 'Login failed.' }));
        }

        res.cookie(TOKEN_COOKIE, data.token, { httpOnly: true, sameSite: 'lax' });
        res.redirect('/profile');
    } catch (err) {
        res.status(502).send(renderAuthPage({ loginError: `Could not reach the backend: ${err.message}` }));
    }
});

router.get('/profile', (req, res) => {
    const token = req.cookies[TOKEN_COOKIE];
    const payload = token && decodeTokenPayload(token);

    if (!payload) {
        return res.redirect('/login');
    }

    const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="auth-nav">
        <a class="logout-button" href="/logout">Log Out</a>
      </div>
      <div class="account-hero">
        <div>
          <h1>Welcome back, ${escapeHtml(payload.username)}!</h1>
          <p><a href="/macros">Calculate your daily macro targets →</a></p>
          <p><a href="/dashboard">View your daily fitness dashboard →</a></p>
          <p><a href="/subscriptions">Manage your weekly meal plan →</a></p>
        </div>
      </div>
    </div>
  </div>`;
    res.send(pageShell('My Profile', body));
});

router.get('/logout', (req, res) => {
    res.clearCookie(TOKEN_COOKIE);
    res.redirect('/login?notice=' + encodeURIComponent('You have been logged out.'));
});

router.get('/reset-request', (req, res) => {
    res.send(renderResetRequestPage({}));
});

router.post('/reset-request', async (req, res) => {
    const { email } = req.body;

    try {
        const backendRes = await fetch(`${BACKEND_URL}/auth/reset-request`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email }),
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.status(backendRes.status).send(renderResetRequestPage({ error: data.error || 'Reset request failed.' }));
        }

        const resetLink = data.reset_token
            ? `/reset-confirm?token=${encodeURIComponent(data.reset_token)}`
            : null;
        res.send(renderResetRequestPage({ message: data.message, resetLink }));
    } catch (err) {
        res.status(502).send(renderResetRequestPage({ error: `Could not reach the backend: ${err.message}` }));
    }
});

router.get('/reset-confirm', (req, res) => {
    const token = req.query.token || '';
    if (!token) {
        return res.redirect('/reset-request');
    }
    res.send(renderResetConfirmPage({ token }));
});

router.post('/reset-confirm', async (req, res) => {
    const { token, new_password } = req.body;

    try {
        const backendRes = await fetch(`${BACKEND_URL}/auth/reset-confirm`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token, new_password }),
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.status(backendRes.status).send(renderResetConfirmPage({ token, error: data.error || 'Reset failed.' }));
        }

        res.redirect('/login?notice=' + encodeURIComponent('Password updated — log in with your new password.'));
    } catch (err) {
        res.status(502).send(renderResetConfirmPage({ token, error: `Could not reach the backend: ${err.message}` }));
    }
});

module.exports = router;
