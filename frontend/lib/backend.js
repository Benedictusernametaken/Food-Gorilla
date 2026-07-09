// Server-side calls to the Flask API. These run inside the Docker network,
// never in the browser, so no CORS handling is needed here.
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:5000';

async function backendRequest(path, { method = 'GET', token, body } = {}) {
    const headers = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${BACKEND_URL}${path}`, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    let data = null;
    try {
        data = await response.json();
    } catch (err) {
        data = null;
    }

    return { status: response.status, data };
}

module.exports = { backendRequest, BACKEND_URL };
