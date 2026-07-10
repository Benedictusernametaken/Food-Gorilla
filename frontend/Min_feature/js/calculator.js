function calculateBMR(weightKg, heightCm, age, gender) {
  if (gender === 'male') {
    return 88.362 + 13.397 * weightKg + 4.799 * heightCm - 5.677 * age;
  }

  return 447.593 + 9.247 * weightKg + 3.098 * heightCm - 4.330 * age;
}

function getActivityMultiplier(activity) {
  const multipliers = {
    sedentary: 1.2,
    lightly: 1.375,
    moderate: 1.55,
    very: 1.725,
    extremely: 1.9
  };
  return multipliers[activity] || 1.2;
}

function getCalorieAdjustment(goal) {
  const adjustments = {
    lose: -500,
    maintain: 0,
    gain: 300
  };
  return adjustments[goal] || 0;
}

function calculateMacros(bmr, activityLevel, goal) {
  const tdee = bmr * activityLevel;
  const calories = Math.round(tdee + getCalorieAdjustment(goal));

  let proteinPercentage = 0.3;
  let carbPercentage = 0.45;
  let fatPercentage = 0.25;

  if (goal === 'lose') {
    proteinPercentage = 0.4;
    fatPercentage = 0.3;
    carbPercentage = 0.3;
  } else if (goal === 'gain') {
    proteinPercentage = 0.3;
    carbPercentage = 0.5;
    fatPercentage = 0.2;
  }

  const protein = Math.round((calories * proteinPercentage) / 4);
  const carbs = Math.round((calories * carbPercentage) / 4);
  const fat = Math.round((calories * fatPercentage) / 9);

  return { calories, protein, carbs, fat };
}

function showFormMessage(message, type = 'error') {
  const formMessage = document.getElementById('formMessage');
  formMessage.className = `form-message ${type}`;
  formMessage.textContent = message;
  formMessage.style.display = 'block';
}

function hideFormMessage() {
  const formMessage = document.getElementById('formMessage');
  formMessage.style.display = 'none';
}

function showAdvice(goal, calories) {
  const adviceText = document.getElementById('adviceText');
  const adviceBox = document.getElementById('adviceBox');
  const resultsSection = document.getElementById('results');

  if (!adviceText || !adviceBox || !resultsSection) {
    return;
  }

  const adviceMap = {
    lose: `Aim for ${calories} kcal/day and focus on lean protein plus fibrous carbs to support healthy weight loss.`,
    maintain: `Aim for ${calories} kcal/day to help maintain your current weight with balanced macros and steady energy.`,
    gain: `Aim for ${calories} kcal/day and add quality protein and nutrient-rich carbs to support muscle gain.`
  };

  adviceText.textContent = adviceMap[goal] || `Your target is ${calories} kcal/day. Keep your meals balanced and stay hydrated.`;
  resultsSection.classList.remove('hidden');
  resultsSection.style.display = 'block';
  adviceBox.classList.remove('hidden');
  adviceBox.style.display = 'block';
}

function updateUnitLabels(units) {
  const weightLabel = document.querySelector('label[for="weight"]');
  const heightLabel = document.querySelector('label[for="height"]');
  const weightInput = document.getElementById('weight');
  const heightInput = document.getElementById('height');

  if (units === 'metric') {
    weightLabel.textContent = 'Weight (kg):';
    heightLabel.textContent = 'Height (cm):';
    weightInput.min = 20;
    heightInput.min = 90;
    weightInput.step = 0.1;
    heightInput.step = 0.1;
  } else {
    weightLabel.textContent = 'Weight (lbs):';
    heightLabel.textContent = 'Height (inches):';
    weightInput.min = 44;
    heightInput.min = 36;
    weightInput.step = 0.1;
    heightInput.step = 0.1;
  }
}

const PROFILES_KEY = 'foodGorillaProfiles';
const CURRENT_PROFILE_KEY = 'foodGorillaCurrentProfile';

function getSavedProfiles() {
  const saved = localStorage.getItem(PROFILES_KEY);
  if (!saved) {
    return [];
  }
  try {
    return JSON.parse(saved);
  } catch (error) {
    localStorage.removeItem(PROFILES_KEY);
    return [];
  }
}

function setSavedProfiles(profiles) {
  localStorage.setItem(PROFILES_KEY, JSON.stringify(profiles));
}

function addSavedProfile(profile) {
  const profiles = [profile, ...getSavedProfiles()];
  if (profiles.length > 10) {
    profiles.pop();
  }
  setSavedProfiles(profiles);
}

function loadSavedProfile() {
  const saved = localStorage.getItem(CURRENT_PROFILE_KEY);
  if (!saved) {
    return;
  }

  try {
    const profile = JSON.parse(saved);
    document.getElementById('units').value = profile.units || 'imperial';
    updateUnitLabels(profile.units || 'imperial');
    document.getElementById('age').value = profile.age || '';
    document.getElementById('gender').value = profile.gender || '';
    document.getElementById('weight').value = profile.weight || '';
    document.getElementById('height').value = profile.height || '';
    document.getElementById('activity').value = profile.activity || '';
    document.getElementById('goal').value = profile.goal || '';
    if (profile.macros) {
      document.getElementById('results').classList.remove('hidden');
      document.getElementById('calorieResult').textContent = profile.macros.calories;
      document.getElementById('proteinResult').textContent = profile.macros.protein;
      document.getElementById('carbsResult').textContent = profile.macros.carbs;
      document.getElementById('fatResult').textContent = profile.macros.fat;
    }
  } catch (error) {
    localStorage.removeItem(CURRENT_PROFILE_KEY);
  }
}

let currentUser = null;

async function fetchCurrentUser() {
  try {
    const response = await fetch('/api/me', { credentials: 'same-origin' });
    if (!response.ok) {
      return null;
    }
    const data = await response.json();
    return data.user || null;
  } catch (error) {
    return null;
  }
}

function saveProfile(profile) {
  localStorage.setItem(CURRENT_PROFILE_KEY, JSON.stringify(profile));
  addSavedProfile(profile);
}

async function requireSignedIn() {
  if (currentUser === null) {
    currentUser = await fetchCurrentUser();
  }
  return Boolean(currentUser);
}

const form = document.getElementById('macroForm');
const unitSelector = document.getElementById('units');

unitSelector.addEventListener('change', (event) => {
  updateUnitLabels(event.target.value);
});

form.addEventListener('submit', async function (e) {
  e.preventDefault();
  hideFormMessage();

  const age = parseInt(document.getElementById('age').value, 10);
  const gender = document.getElementById('gender').value;
  const units = document.getElementById('units').value;
  const weight = parseFloat(document.getElementById('weight').value);
  const height = parseFloat(document.getElementById('height').value);
  const activity = document.getElementById('activity').value;
  const goal = document.getElementById('goal').value;

  if (!Number.isFinite(age) || !gender || !units || !weight || !height || !activity || !goal) {
    showFormMessage('Please complete every field before calculating.');
    return;
  }

  const weightKg = units === 'metric' ? weight : weight * 0.453592;
  const heightCm = units === 'metric' ? height : height * 2.54;

  const bmr = calculateBMR(weightKg, heightCm, age, gender);
  const activityMultiplier = getActivityMultiplier(activity);
  const macros = calculateMacros(bmr, activityMultiplier, goal);

  document.getElementById('calorieResult').textContent = macros.calories;
  document.getElementById('proteinResult').textContent = macros.protein;
  document.getElementById('carbsResult').textContent = macros.carbs;
  document.getElementById('fatResult').textContent = macros.fat;
  document.getElementById('results').classList.remove('hidden');
  showAdvice(goal, macros.calories);
  document.getElementById('results').scrollIntoView({ behavior: 'smooth' });

  const profile = {
    id: `profile-${Date.now()}`,
    name: `${goal.charAt(0).toUpperCase() + goal.slice(1)} profile`,
    units,
    age,
    gender,
    weight,
    height,
    activity,
    goal,
    macros,
    timestamp: new Date().toISOString()
  };

  if (await requireSignedIn()) {
    saveProfile(profile);
    updateSavedProfilesUI();
    showFormMessage('Profile saved successfully.', 'success');
  } else {
    showFormMessage('Sign in to save your macro profile.', 'error');
  }
});

function createProfileItem(profile) {
  const item = document.createElement('div');
  item.className = 'saved-profile-item';
  item.innerHTML = `
    <div class="profile-meta">
      <div class="profile-name">${profile.name}</div>
      <div class="profile-date">${new Date(profile.timestamp).toLocaleString()}</div>
    </div>
    <div class="profile-actions">
      <button type="button" data-id="${profile.id}" class="load-profile">Load</button>
      <button type="button" data-id="${profile.id}" class="delete-profile">Delete</button>
    </div>
  `;
  return item;
}

function updateSavedProfilesUI() {
  const profiles = getSavedProfiles();
  const list = document.getElementById('savedProfilesList');
  const empty = document.getElementById('profilesEmpty');

  list.innerHTML = '';
  if (!profiles.length) {
    empty.style.display = 'block';
    return;
  }

  empty.style.display = 'none';
  profiles.forEach((profile) => {
    const item = createProfileItem(profile);
    list.appendChild(item);
  });

  list.querySelectorAll('.load-profile').forEach((button) => {
    button.addEventListener('click', (event) => {
      const profileId = event.target.dataset.id;
      const profile = profiles.find((entry) => entry.id === profileId);
      if (!profile) return;
      localStorage.setItem(CURRENT_PROFILE_KEY, JSON.stringify(profile));
      loadSavedProfile();
      showFormMessage(`Loaded profile: ${profile.name}`, 'success');
    });
  });

  list.querySelectorAll('.delete-profile').forEach((button) => {
    button.addEventListener('click', (event) => {
      const profileId = event.target.dataset.id;
      const remaining = profiles.filter((entry) => entry.id !== profileId);
      setSavedProfiles(remaining);
      updateSavedProfilesUI();
    });
  });
}

loadSavedProfile();
updateSavedProfilesUI();
