const express = require('express');
const router = express.Router();

// Set via docker-compose.yml -> resolves to the backend container over
// Docker's internal network. Never hardcode this.
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:5000';

// Same cookie Story 7's auth.js sets on login/signup.
const TOKEN_COOKIE = 'fg_token';

const GOAL_LABELS = {
    lose_weight: 'Lose Weight',
    maintain: 'Maintain',
    gain_muscle: 'Gain Muscle',
};

const GOAL_ADVICE = {
    lose_weight: 'You\'re in a calorie deficit with extra protein to help preserve muscle while you lose fat.',
    maintain: 'These targets are set at your maintenance level to keep your weight steady.',
    gain_muscle: 'You\'re in a calorie surplus with extra carbs to fuel training and support muscle growth.',
};

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
}

// Decodes the JWT payload for display purposes only. The signature is
// never checked here — every backend call below sends the raw token and
// lets the backend be the actual trust boundary.
function decodeTokenPayload(token) {
    try {
        const payloadSegment = token.split('.')[1];
        const json = Buffer.from(payloadSegment, 'base64url').toString('utf-8');
        return JSON.parse(json);
    } catch (err) {
        console.error(err);
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

function requireUserToken(req, res) {
    const token = req.cookies[TOKEN_COOKIE];
    const payload = token && decodeTokenPayload(token);
    if (!payload) {
        res.redirect('/login');
        return null;
    }
    return token;
}

async function backendFetch(token, path, options = {}) {
    return fetch(`${BACKEND_URL}${path}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            ...(options.headers || {}),
        },
    });
}

function renderResults(profile) {
    if (!profile) return '';
    const advice = GOAL_ADVICE[profile.goal] || '';
    return `
      <div class="results">
        <h2>Your Daily Targets</h2>
        <div class="macro-grid">
          <div class="macro-card">
            <h3>Calories</h3>
            <div class="macro-value">${profile.calories}</div>
            <div class="macro-unit">kcal</div>
          </div>
          <div class="macro-card">
            <h3>Protein</h3>
            <div class="macro-value">${profile.protein_g}</div>
            <div class="macro-unit">grams</div>
          </div>
          <div class="macro-card">
            <h3>Carbs</h3>
            <div class="macro-value">${profile.carbs_g}</div>
            <div class="macro-unit">grams</div>
          </div>
          <div class="macro-card">
            <h3>Fats</h3>
            <div class="macro-value">${profile.fats_g}</div>
            <div class="macro-unit">grams</div>
          </div>
        </div>
        ${advice ? `<div class="advice-box"><h3>Advice</h3><p>${escapeHtml(advice)}</p></div>` : ''}
      </div>`;
}

function renderCalculatorForm(values = {}) {
    return `
      <form method="POST" action="/macros">
        <fieldset>
          <legend>Your Metrics</legend>
          <div class="form-group">
            <label>Age</label>
            <input type="number" name="age" min="13" max="100" value="${escapeHtml(values.age)}" required>
          </div>
          <div class="form-group">
            <label>Gender</label>
            <select name="gender" required>
              <option value="">Select…</option>
              <option value="male" ${values.gender === 'male' ? 'selected' : ''}>Male</option>
              <option value="female" ${values.gender === 'female' ? 'selected' : ''}>Female</option>
              <option value="other" ${values.gender === 'other' ? 'selected' : ''}>Other</option>
            </select>
          </div>
          <div class="form-group">
            <label>Weight (kg)</label>
            <input type="number" step="0.1" name="weight_kg" min="30" max="300" value="${escapeHtml(values.weight_kg)}" required>
          </div>
          <div class="form-group">
            <label>Height (cm)</label>
            <input type="number" step="0.1" name="height_cm" min="100" max="250" value="${escapeHtml(values.height_cm)}" required>
          </div>
          <div class="form-group">
            <label>Activity Level</label>
            <select name="activity_level" required>
              <option value="">Select…</option>
              <option value="sedentary" ${values.activity_level === 'sedentary' ? 'selected' : ''}>Sedentary (little/no exercise)</option>
              <option value="light" ${values.activity_level === 'light' ? 'selected' : ''}>Light (1-3 days/week)</option>
              <option value="moderate" ${values.activity_level === 'moderate' ? 'selected' : ''}>Moderate (3-5 days/week)</option>
              <option value="active" ${values.activity_level === 'active' ? 'selected' : ''}>Active (6-7 days/week)</option>
              <option value="very_active" ${values.activity_level === 'very_active' ? 'selected' : ''}>Very Active (physical job + training)</option>
            </select>
          </div>
        </fieldset>
        <fieldset>
          <legend>Your Goal</legend>
          <div class="form-group">
            <select name="goal" required>
              <option value="">Select…</option>
              <option value="lose_weight" ${values.goal === 'lose_weight' ? 'selected' : ''}>Lose Weight</option>
              <option value="maintain" ${values.goal === 'maintain' ? 'selected' : ''}>Maintain</option>
              <option value="gain_muscle" ${values.goal === 'gain_muscle' ? 'selected' : ''}>Gain Muscle</option>
            </select>
          </div>
        </fieldset>
        <button type="submit" class="btn-submit">Calculate My Macros</button>
      </form>`;
}

function renderSavedProfile(profile) {
    const goalLabel = GOAL_LABELS[profile.goal] || '';
    return `
    <div class="saved-profile-item">
      <div class="profile-meta">
        <div class="profile-name">${profile.calories} kcal${goalLabel ? ` — ${escapeHtml(goalLabel)}` : ''}</div>
        <div class="profile-date">${profile.protein_g}g protein · ${profile.carbs_g}g carbs · ${profile.fats_g}g fats</div>
        <div class="profile-date">Saved ${profile.updated_at ? new Date(profile.updated_at).toLocaleString() : ''}</div>
      </div>
      <div class="profile-actions">
        <form method="POST" action="/macros/${profile.profile_id}/delete" style="display:inline">
          <button type="submit" class="delete-profile">Delete</button>
        </form>
      </div>
    </div>`;
}

router.get('/macros', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    try {
        const backendRes = await backendFetch(token, '/profile/macros');
        const data = await backendRes.json();

        if (!backendRes.ok) {
            return res.status(backendRes.status).send(pageShell('Macro Calculator', `<p>${escapeHtml(data.error || 'Failed to load saved profiles.')}</p>`));
        }

        const savedHtml = data.profiles.length
            ? data.profiles.map(renderSavedProfile).join('')
            : '<p class="empty-state">No saved profiles yet — calculate your targets below.</p>';

        const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="auth-nav">
        <a class="nav-link" href="/profile">Back to Profile</a>
        <a class="logout-button" href="/logout">Log Out</a>
      </div>
      <div class="account-hero">
        <h1>Macro Calculator</h1>
        <p>Input your metrics and goal to get your daily calorie and macro targets.</p>
      </div>
      <main>
        ${renderCalculatorForm()}
      </main>
      <div class="saved-profiles-section">
        <h2 class="section-label">Saved Profiles</h2>
        <div class="saved-profiles-list">${savedHtml}</div>
      </div>
    </div>
  </div>`;
        res.send(pageShell('Macro Calculator', body));
    } catch (err) {
        res.status(502).send(pageShell('Macro Calculator', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

router.post('/macros', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    const { age, gender, weight_kg, height_cm, activity_level, goal } = req.body;

    try {
        const backendRes = await backendFetch(token, '/profile/macros', {
            method: 'POST',
            body: JSON.stringify({ age, gender, weight_kg, height_cm, activity_level, goal }),
        });
        const data = await backendRes.json();

        if (!backendRes.ok) {
            const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="account-hero">
        <h1>Macro Calculator</h1>
      </div>
      <main>
        ${renderCalculatorForm({ age, gender, weight_kg, height_cm, activity_level, goal })}
        <div class="auth-message error">${escapeHtml(data.error || 'Calculation failed.')}</div>
      </main>
    </div>
  </div>`;
            return res.status(backendRes.status).send(pageShell('Macro Calculator', body));
        }

        const body = `
  <div class="auth-shell">
    <div class="auth-card auth-production-card">
      <div class="auth-nav">
        <a class="nav-link" href="/macros">Back to Calculator</a>
      </div>
      <div class="account-hero">
        <h1>Your Targets Are Saved!</h1>
      </div>
      ${renderResults({ ...data, goal })}
    </div>
  </div>`;
        res.send(pageShell('Your Macro Targets', body));
    } catch (err) {
        res.status(502).send(pageShell('Macro Calculator', `<p>Could not reach the backend: ${escapeHtml(err.message)}</p>`));
    }
});

router.post('/macros/:id/delete', async (req, res) => {
    const token = requireUserToken(req, res);
    if (!token) return;

    try {
        await backendFetch(token, `/profile/macros/${req.params.id}`, { method: 'DELETE' });
    } catch (err) {
        console.error(err);
        // Fall through — the redirect below will simply still show the item,
        // which is an honest reflection of the delete not having gone through.
    }
    res.redirect('/macros');
});

module.exports = router;
