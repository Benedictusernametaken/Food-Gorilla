const express = require('express');
const path = require('path');
const app = express();
const PORT = 3000;

// Set via docker-compose.yml -> resolves to the backend container over
// Docker's internal network. Never hardcode this — it changes between
// local/test/prod the same way DATABASE_URL does on the backend.
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:5000';

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

function parseCookies(req) {
    const cookieHeader = req.headers.cookie || '';
    return Object.fromEntries(
        cookieHeader.split(';').map((entry) => entry.trim()).filter(Boolean).map((entry) => {
            const [name, ...rest] = entry.split('=');
            return [name, rest.join('=')];
        })
    );
}

function setAuthCookie(res, token) {
    res.setHeader('Set-Cookie', `auth_token=${token}; Path=/; HttpOnly; Max-Age=86400; SameSite=Lax`);
}

function clearAuthCookie(res) {
    res.setHeader('Set-Cookie', 'auth_token=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax');
}

function renderViewWithAuth(res, req, view, locals = {}) {
    const cookies = parseCookies(req);
    const token = cookies.auth_token;
    return res.render(view, { isAuthenticated: Boolean(token), ...locals });
}

async function fetchBackend(path, options = {}) {
    const response = await fetch(`${BACKEND_URL}${path}`, {
        headers: {
            'Content-Type': 'application/json',
            ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
        },
        ...options,
        body: options.body ? (typeof options.body === 'string' ? options.body : JSON.stringify(options.body)) : undefined,
    });

    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json') ? await response.json() : await response.text();
    return { response, data };
}

async function getMeals() {
    const { response, data } = await fetchBackend('/meals');
    if (!response.ok) {
        throw new Error(data.error || 'Unable to load meals.');
    }
    return data;
}

app.get('/', (req, res) => {
    res.redirect('/menu');
});

app.get('/menu', async (req, res) => {
    try {
        const meals = await getMeals();
        renderViewWithAuth(res, req, 'menu', { meals, error: null, active: 'menu' });
    } catch (err) {
        res.status(502);
        renderViewWithAuth(res, req, 'menu', { meals: [], error: err.message, active: 'menu' });
    }
});

app.get('/register', (req, res) => {
    renderViewWithAuth(res, req, 'register', { active: 'register', error: null, form: {} });
});

app.post('/register', async (req, res) => {
    try {
        const { response, data } = await fetchBackend('/register', {
            method: 'POST',
            body: req.body,
        });

        if (!response.ok) {
            res.status(response.status);
            return renderViewWithAuth(res, req, 'register', {
                active: 'register',
                error: data.error || 'Registration failed.',
                form: req.body,
            });
        }

        res.redirect('/login');
    } catch (err) {
        res.status(502);
        renderViewWithAuth(res, req, 'register', {
            active: 'register',
            error: err.message,
            form: req.body,
        });
    }
});

app.get('/login', (req, res) => {
    renderViewWithAuth(res, req, 'login', { active: 'login', error: null, form: {} });
});

app.post('/login', async (req, res) => {
    try {
        const { response, data } = await fetchBackend('/login', {
            method: 'POST',
            body: req.body,
        });

        if (!response.ok) {
            res.status(response.status);
            return renderViewWithAuth(res, req, 'login', {
                active: 'login',
                error: data.error || 'Login failed.',
                form: req.body,
            });
        }

        setAuthCookie(res, data.token);
        res.redirect('/dashboard');
    } catch (err) {
        res.status(502);
        renderViewWithAuth(res, req, 'login', {
            active: 'login',
            error: err.message,
            form: req.body,
        });
    }
});

app.get('/checkout', async (req, res) => {
    const cookies = parseCookies(req);
    const token = cookies.auth_token;

    if (!token) {
        return res.redirect('/login');
    }

    try {
        const meals = await getMeals();
        renderViewWithAuth(res, req, 'checkout', { active: 'checkout', meals, error: null, success: null, alerts: [] });
    } catch (err) {
        res.status(502);
        renderViewWithAuth(res, req, 'checkout', { active: 'checkout', meals: [], error: null, success: null, alerts: [] });
    }
});

async function getDashboard(token) {
    const { response, data } = await fetchBackend('/dashboard', {
        token,
    });

    if (!response.ok) {
        throw new Error(data.error || 'Unable to load dashboard.');
    }

    return data;
}

app.get('/dashboard', async (req, res) => {
    const cookies = parseCookies(req);
    const token = cookies.auth_token;

    if (!token) {
        return res.redirect('/login');
    }

    try {
        const dashboard = await getDashboard(token);
        renderViewWithAuth(res, req, 'dashboard', { active: 'dashboard', dashboard, error: null });
    } catch (err) {
        res.status(502);
        renderViewWithAuth(res, req, 'dashboard', { active: 'dashboard', dashboard: null, error: err.message });
    }
});

app.post('/checkout', async (req, res) => {
    const cookies = parseCookies(req);
    const token = cookies.auth_token;

    if (!token) {
        return res.redirect('/login');
    }

    try {
        const { response, data } = await fetchBackend('/checkout', {
            method: 'POST',
            token,
            body: req.body,
        });

        const meals = await getMeals();
        if (!response.ok) {
            res.status(response.status);
            return renderViewWithAuth(res, req, 'checkout', {
                active: 'checkout',
                meals,
                error: data.error || 'Checkout failed.',
                success: null,
                alerts: [],
            });
        }

        renderViewWithAuth(res, req, 'checkout', {
            active: 'checkout',
            meals,
            error: null,
            success: data.message || 'Order placed successfully.',
            alerts: data.alerts || [],
        });
    } catch (err) {
        const meals = await getMeals().catch(() => []);
        res.status(502);
        renderViewWithAuth(res, req, 'checkout', {
            active: 'checkout',
            meals,
            error: null,
            success: null,
            alerts: [],
        });
    }
});

app.get('/logout', (req, res) => {
    clearAuthCookie(res);
    res.redirect('/login');
});

app.listen(PORT, () => {
    console.log(`Frontend UI server running on http://localhost:${PORT}`);
});