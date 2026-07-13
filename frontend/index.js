const express = require('express');
const app = express();
const PORT = 3000;

// Set via docker-compose.yml -> resolves to the backend container over
// Docker's internal network. Never hardcode this — it changes between
// local/test/prod the same way DATABASE_URL does on the backend.
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:5000';

app.get('/', async (req, res) => {
    try {
        // Server-side call: this request happens inside the Docker network,
        // never in the user's browser, so no CORS setup is needed.
        const response = await fetch(`${BACKEND_URL}/health-check`);
        const data = await response.json();

        res.send(`
            <h1>Welcome to the Food Gorilla Frontend Tier!</h1>
            <p>Backend status: ${data.status}</p>
            <p>Database connectivity (via backend): ${data.database_connectivity}</p>
        `);
    } catch (err) {
        // Frontend container itself is fine — it's the backend that's
        // unreachable. Keeping this distinction visible matters for debugging.
        res.status(502).send(`
            <h1>Food Gorilla Frontend is running</h1>
            <p>But the backend could not be reached: ${err.message}</p>
        `);
    }
});

app.listen(PORT, () => {
    console.log(`Frontend UI server running on http://localhost:${PORT}`);
});