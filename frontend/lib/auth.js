// httpOnly cookie holding the Flask-issued bearer token. The browser never
// reads it directly — client JS calls same-origin /api/dashboard/* routes,
// which read this cookie server-side and forward it as an Authorization header.
const TOKEN_COOKIE = 'vendor_token';

function requireLoginPage(req, res, next) {
    const token = req.cookies[TOKEN_COOKIE];
    if (!token) return res.redirect('/login');
    req.vendorToken = token;
    next();
}

function requireLoginApi(req, res, next) {
    const token = req.cookies[TOKEN_COOKIE];
    if (!token) return res.status(401).json({ error: 'Not logged in' });
    req.vendorToken = token;
    next();
}

module.exports = { TOKEN_COOKIE, requireLoginPage, requireLoginApi };
