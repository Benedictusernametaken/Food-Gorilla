const express = require('express');
const router = express.Router();
const { backendRequest } = require('../lib/backend');
const { TOKEN_COOKIE } = require('../lib/auth');
const { pageShell } = require('../views/layout');

function loginPage({ error = '' } = {}) {
    return pageShell({
        title: 'Merchant Login',
        activeNav: 'dashboard',
        bodyHtml: `
          <div class="card login-card">
            <h1>Merchant Login</h1>
            <p class="muted">Demo account: owner@leanmean.com / password123</p>
            ${error ? `<p class="error">${error}</p>` : ''}
            <form method="POST" action="/login">
              <label>Email
                <input type="email" name="email" required autofocus>
              </label>
              <label>Password
                <input type="password" name="password" required>
              </label>
              <button type="submit">Log In</button>
            </form>
          </div>
        `,
    });
}

router.get('/login', (req, res) => {
    if (req.cookies[TOKEN_COOKIE]) return res.redirect('/dashboard');
    res.send(loginPage());
});

router.post('/login', async (req, res) => {
    const { email, password } = req.body;
    const { status, data } = await backendRequest('/api/auth/login', {
        method: 'POST',
        body: { email, password },
    });

    if (status !== 200) {
        return res.status(status === 401 ? 401 : 400).send(
            loginPage({ error: (data && data.error) || 'Login failed' })
        );
    }

    res.cookie(TOKEN_COOKIE, data.token, {
        httpOnly: true,
        sameSite: 'lax',
        expires: new Date(data.expires_at),
    });
    res.redirect('/dashboard');
});

router.post('/logout', async (req, res) => {
    const token = req.cookies[TOKEN_COOKIE];
    if (token) {
        await backendRequest('/api/auth/logout', { method: 'POST', token });
    }
    res.clearCookie(TOKEN_COOKIE);
    res.redirect('/login');
});

module.exports = router;
