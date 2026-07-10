const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = (process.env.BACKEND_URL || process.env.BACKEND_HOST || 'http://127.0.0.1:5000').replace(/\/$/, '');

function parseCookies(req) {
  const cookieHeader = req.headers.cookie || '';
  return Object.fromEntries(
    cookieHeader
      .split(';')
      .map((entry) => entry.trim())
      .filter(Boolean)
      .map((entry) => {
        const [name, ...rest] = entry.split('=');
        return [name, rest.join('=')];
      })
  );
}

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

app.get('/health-check', async (req, res) => {
  try {
    const response = await fetch(`${BACKEND_URL}/health-check`);
    const data = await response.json();
    res.json({ status: 'ok', backend: data });
  } catch (err) {
    res.status(502).json({ status: 'error', message: err.message });
  }
});

app.use('/api', async (req, res) => {
  const targetUrl = `${BACKEND_URL}${req.originalUrl}`;
  const cookies = parseCookies(req);
  const token = cookies.auth_token || '';

  try {
    const headers = {
  'Content-Type': 'application/json',
  ...(token ? { 'X-Session-Token': token } : {}),
    };

    const response = await fetch(targetUrl, {
      method: req.method,
      headers,
      body: req.method === 'GET' || req.method === 'HEAD' ? undefined : JSON.stringify(req.body),
    });

    const contentType = response.headers.get('content-type') || '';
    const body = contentType.includes('application/json') ? await response.json() : await response.text();
    res.status(response.status).send(body);
  } catch (err) {
    res.status(502).json({ error: `Backend unavailable: ${err.message}` });
  }
});

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Frontend UI server running on http://localhost:${PORT}`);
});