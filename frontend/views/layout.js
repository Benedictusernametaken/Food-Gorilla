function pageShell({ title, activeNav = '', bodyHtml, extraScripts = [] }) {
    const navLink = (href, label, key) =>
        `<a href="${href}" class="${activeNav === key ? 'active' : ''}">${label}</a>`;

    const scripts = extraScripts.map(src => `<script src="${src}" defer></script>`).join('\n');

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title} · Food Gorilla</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <nav class="site-nav">
    <a href="/" class="brand">🦍 Food Gorilla</a>
    <div class="nav-links">
      ${navLink('/', 'Marketplace', 'marketplace')}
      ${navLink('/dashboard', 'Merchant Dashboard', 'dashboard')}
    </div>
  </nav>
  <main class="page">
    ${bodyHtml}
  </main>
  ${scripts}
</body>
</html>`;
}

module.exports = { pageShell };
