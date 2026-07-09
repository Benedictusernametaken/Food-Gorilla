const express = require('express');
const cookieParser = require('cookie-parser');
const path = require('path');

const { backendRequest } = require('./lib/backend');
const { pageShell } = require('./views/layout');
const marketplaceRoutes = require('./routes/marketplace');
const authRoutes = require('./routes/auth');
const dashboardRoutes = require('./routes/dashboard');

const app = express();
const PORT = 3000;

app.use(express.json());
app.use(express.urlencoded({ extended: false }));
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));

app.use(marketplaceRoutes);
app.use(authRoutes);
app.use(dashboardRoutes);

// Lightweight system status page, kept from the original health-check demo.
app.get('/status', async (req, res) => {
    const { data } = await backendRequest('/health-check');
    res.send(pageShell({
        title: 'System Status',
        bodyHtml: `
          <h1>System Status</h1>
          <p>Backend status: ${data ? data.status : 'unreachable'}</p>
          <p>Database connectivity: ${data ? data.database_connectivity : 'n/a'}</p>
        `,
    }));
});

app.listen(PORT, () => {
    console.log(`Frontend UI server running on http://localhost:${PORT}`);
});
