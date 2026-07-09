const resultsEl = document.getElementById('results');
const formEl = document.getElementById('search-form');
const qField = document.getElementById('search-q');
const maxCaloriesField = document.getElementById('max-calories');
const minProteinField = document.getElementById('min-protein');
const maxPriceField = document.getElementById('max-price');

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : str;
    return div.innerHTML;
}

function mealCard(meal) {
    const card = document.createElement('article');
    card.className = 'meal-card';
    card.innerHTML = `
      <h3>${escapeHtml(meal.name)}</h3>
      <p class="muted">${escapeHtml(meal.restaurant_name)}</p>
      ${meal.description ? `<p>${escapeHtml(meal.description)}</p>` : ''}
      <div class="macro-row">
        <span>${meal.base_calories} cal</span>
        <span>${meal.base_protein}g protein</span>
        <span>${meal.base_carbs}g carbs</span>
        <span>${meal.base_fats}g fat</span>
      </div>
      <div class="price">$${Number(meal.base_price).toFixed(2)}</div>
    `;
    return card;
}

async function search() {
    const params = new URLSearchParams();
    if (qField.value.trim()) params.set('q', qField.value.trim());
    if (maxCaloriesField.value) params.set('max_calories', maxCaloriesField.value);
    if (minProteinField.value) params.set('min_protein', minProteinField.value);
    if (maxPriceField.value) params.set('max_price', maxPriceField.value);

    resultsEl.innerHTML = '<p class="muted">Searching…</p>';
    const res = await fetch(`/api/marketplace/search?${params.toString()}`);
    const meals = await res.json();

    resultsEl.innerHTML = '';
    if (!Array.isArray(meals) || !meals.length) {
        resultsEl.innerHTML = '<p class="muted">No meals match those filters.</p>';
        return;
    }
    meals.forEach(meal => resultsEl.appendChild(mealCard(meal)));
}

formEl.addEventListener('submit', (e) => {
    e.preventDefault();
    search();
});

search();
