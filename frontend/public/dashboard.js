const rowsEl = document.getElementById('meal-rows');
const formEl = document.getElementById('meal-form');
const formTitle = document.getElementById('form-title');
const formError = document.getElementById('form-error');
const formSubmit = document.getElementById('form-submit');
const formCancel = document.getElementById('form-cancel');
const idField = document.getElementById('meal-id');
const nameField = document.getElementById('meal-name');
const descField = document.getElementById('meal-description');
const priceField = document.getElementById('meal-price');
const caloriesField = document.getElementById('meal-calories');
const proteinField = document.getElementById('meal-protein');
const carbsField = document.getElementById('meal-carbs');
const fatsField = document.getElementById('meal-fats');
const availableField = document.getElementById('meal-available');
const vendorNameEl = document.getElementById('vendor-name');

let meals = [];

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : str;
    return div.innerHTML;
}

function showError(message) {
    formError.textContent = message;
    formError.classList.toggle('hidden', !message);
}

function resetForm() {
    formEl.reset();
    idField.value = '';
    availableField.checked = true;
    formTitle.textContent = 'Add Menu Item';
    formSubmit.textContent = 'Add Item';
    formCancel.classList.add('hidden');
    showError('');
}

function fillForm(meal) {
    idField.value = meal.meal_id;
    nameField.value = meal.name;
    descField.value = meal.description || '';
    priceField.value = meal.base_price;
    caloriesField.value = meal.base_calories;
    proteinField.value = meal.base_protein;
    carbsField.value = meal.base_carbs;
    fatsField.value = meal.base_fats;
    availableField.checked = meal.is_available;
    formTitle.textContent = `Edit "${meal.name}"`;
    formSubmit.textContent = 'Save Changes';
    formCancel.classList.remove('hidden');
    showError('');
    nameField.focus();
}

function mealRow(meal) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${escapeHtml(meal.name)}</td>
      <td>$${Number(meal.base_price).toFixed(2)}</td>
      <td>${meal.base_calories}</td>
      <td>${meal.base_protein}g</td>
      <td>${meal.base_carbs}g</td>
      <td>${meal.base_fats}g</td>
      <td>
        <label class="switch">
          <input type="checkbox" ${meal.is_available ? 'checked' : ''} data-id="${meal.meal_id}" class="availability-toggle">
          <span class="slider"></span>
        </label>
      </td>
      <td class="row-actions">
        <button type="button" class="link edit-btn" data-id="${meal.meal_id}">Edit</button>
        <button type="button" class="link danger delete-btn" data-id="${meal.meal_id}">Delete</button>
      </td>
    `;
    return tr;
}

function renderRows() {
    rowsEl.innerHTML = '';
    if (!meals.length) {
        rowsEl.innerHTML = '<tr><td colspan="8" class="muted">No menu items yet — add your first one above.</td></tr>';
        return;
    }
    meals.forEach(meal => rowsEl.appendChild(mealRow(meal)));
}

async function loadVendor() {
    const res = await fetch('/api/dashboard/me');
    if (res.status === 401) return (window.location.href = '/login');
    const vendor = await res.json();
    vendorNameEl.textContent = `${vendor.restaurant_name} · ${vendor.email}`;
}

async function loadMeals() {
    const res = await fetch('/api/dashboard/meals');
    if (res.status === 401) return (window.location.href = '/login');
    meals = await res.json();
    renderRows();
}

formEl.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
        name: nameField.value.trim(),
        description: descField.value.trim(),
        base_price: priceField.value,
        base_calories: caloriesField.value,
        base_protein: proteinField.value,
        base_carbs: carbsField.value,
        base_fats: fatsField.value,
        is_available: availableField.checked,
    };

    const mealId = idField.value;
    const url = mealId ? `/api/dashboard/meals/${mealId}` : '/api/dashboard/meals';
    const method = mealId ? 'PUT' : 'POST';

    const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
        showError((data.errors && data.errors.join(', ')) || data.error || 'Something went wrong');
        return;
    }

    resetForm();
    await loadMeals();
});

formCancel.addEventListener('click', resetForm);

rowsEl.addEventListener('click', async (e) => {
    const editBtn = e.target.closest('.edit-btn');
    const deleteBtn = e.target.closest('.delete-btn');

    if (editBtn) {
        const meal = meals.find(m => String(m.meal_id) === editBtn.dataset.id);
        if (meal) fillForm(meal);
    }

    if (deleteBtn) {
        if (!confirm('Delete this menu item? This cannot be undone.')) return;
        const res = await fetch(`/api/dashboard/meals/${deleteBtn.dataset.id}`, { method: 'DELETE' });
        if (res.ok) await loadMeals();
    }
});

rowsEl.addEventListener('change', async (e) => {
    if (!e.target.classList.contains('availability-toggle')) return;
    const mealId = e.target.dataset.id;
    const isAvailable = e.target.checked;

    const res = await fetch(`/api/dashboard/meals/${mealId}/availability`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_available: isAvailable }),
    });

    if (res.ok) {
        const meal = meals.find(m => String(m.meal_id) === mealId);
        if (meal) meal.is_available = isAvailable;
    } else {
        e.target.checked = !isAvailable;
    }
});

resetForm();
loadVendor();
loadMeals();
