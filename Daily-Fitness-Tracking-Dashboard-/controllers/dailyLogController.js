const { get, run, all } = require('../config/db');

const MACROS = [
  { key: 'calories', consumedColumn: 'consumed_calories', targetColumn: 'target_calories', requestKey: 'calories' },
  { key: 'protein', consumedColumn: 'consumed_protein_g', targetColumn: 'target_protein_g', requestKey: 'protein_g' },
  { key: 'carbs', consumedColumn: 'consumed_carbs_g', targetColumn: 'target_carbs_g', requestKey: 'carbs_g' },
  { key: 'fats', consumedColumn: 'consumed_fats_g', targetColumn: 'target_fats_g', requestKey: 'fats_g' },
];

function calculateMacroAlertStatus(consumed, target) {
  if (target <= 0) {
    return 'green';
  }
  const percent = Math.round((consumed / target) * 100);
  if (percent >= 100) return 'red';
  if (percent >= 75) return 'yellow';
  return 'green';
}

function getTierRank(tier) {
  if (tier === 'red') return 2;
  if (tier === 'yellow') return 1;
  return 0;
}

function buildMacroResponse(consumed, target) {
  const percent = target > 0 ? Math.round((consumed / target) * 100) : 0;
  const tier = calculateMacroAlertStatus(consumed, target);
  return {
    consumed,
    target,
    percent,
    tier,
  };
}

async function getDailyLog(req, res) {
  const userId = Number(req.query.user_id);
  const date = req.query.date;

  if (!userId || !date) {
    return res.status(400).json({ error: 'user_id and date are required query parameters' });
  }

  const user = await get('SELECT * FROM Users WHERE user_id = ?', [userId]);
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }

  const log = await get('SELECT * FROM Daily_Logs WHERE user_id = ? AND date = ?', [userId, date]);
  const consumedValues = {
    calories: log ? log.consumed_calories : 0,
    protein: log ? log.consumed_protein_g : 0,
    carbs: log ? log.consumed_carbs_g : 0,
    fats: log ? log.consumed_fats_g : 0,
  };

  const response = {
    calories: buildMacroResponse(consumedValues.calories, user.target_calories),
    protein: buildMacroResponse(consumedValues.protein, user.target_protein_g),
    carbs: buildMacroResponse(consumedValues.carbs, user.target_carbs_g),
    fats: buildMacroResponse(consumedValues.fats, user.target_fats_g),
  };

  return res.json(response);
}

async function getDailyLogHistory(req, res) {
  const userId = Number(req.query.user_id);
  const days = Number(req.query.days) || 7;

  if (!userId || days <= 0) {
    return res.status(400).json({ error: 'user_id and positive days are required' });
  }

  const user = await get('SELECT * FROM Users WHERE user_id = ?', [userId]);
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }

  const today = new Date();
  const dates = [];
  for (let i = days - 1; i >= 0; i -= 1) {
    const day = new Date(today);
    day.setDate(today.getDate() - i);
    dates.push(day.toISOString().slice(0, 10));
  }

  const rows = await all(
    `SELECT * FROM Daily_Logs WHERE user_id = ? AND date IN (${dates.map(() => '?').join(',')}) ORDER BY date ASC`,
    [userId, ...dates]
  );

  const rowMap = rows.reduce((map, row) => {
    map[row.date] = row;
    return map;
  }, {});

  const history = dates.map((date) => {
    const row = rowMap[date];
    return {
      date,
      consumed_calories: row ? row.consumed_calories : 0,
      consumed_protein_g: row ? row.consumed_protein_g : 0,
      consumed_carbs_g: row ? row.consumed_carbs_g : 0,
      consumed_fats_g: row ? row.consumed_fats_g : 0,
      target_calories: user.target_calories,
      target_protein_g: user.target_protein_g,
      target_carbs_g: user.target_carbs_g,
      target_fats_g: user.target_fats_g,
    };
  });

  return res.json(history);
}

async function completeOrder(req, res) {
  const { user_id, calories, protein_g, carbs_g, fats_g } = req.body;
  const userId = Number(user_id);
  const caloriesValue = Number(calories);
  const proteinValue = Number(protein_g);
  const carbsValue = Number(carbs_g);
  const fatsValue = Number(fats_g);

  if (!userId || Number.isNaN(caloriesValue) || Number.isNaN(proteinValue) || Number.isNaN(carbsValue) || Number.isNaN(fatsValue)) {
    return res.status(400).json({ error: 'user_id, calories, protein_g, carbs_g, and fats_g are required and must be numbers' });
  }

  const user = await get('SELECT * FROM Users WHERE user_id = ?', [userId]);
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }

  const date = new Date().toISOString().slice(0, 10);
  const existingLog = await get('SELECT * FROM Daily_Logs WHERE user_id = ? AND date = ?', [userId, date]);

  const previousTotals = {
    calories: existingLog ? existingLog.consumed_calories : 0,
    protein: existingLog ? existingLog.consumed_protein_g : 0,
    carbs: existingLog ? existingLog.consumed_carbs_g : 0,
    fats: existingLog ? existingLog.consumed_fats_g : 0,
  };

  const updatedTotals = {
    calories: previousTotals.calories + caloriesValue,
    protein: previousTotals.protein + proteinValue,
    carbs: previousTotals.carbs + carbsValue,
    fats: previousTotals.fats + fatsValue,
  };

  if (existingLog) {
    await run(
      `UPDATE Daily_Logs SET consumed_calories = ?, consumed_protein_g = ?, consumed_carbs_g = ?, consumed_fats_g = ? WHERE log_id = ?`,
      [updatedTotals.calories, updatedTotals.protein, updatedTotals.carbs, updatedTotals.fats, existingLog.log_id]
    );
  } else {
    await run(
      `INSERT INTO Daily_Logs (user_id, date, consumed_calories, consumed_protein_g, consumed_carbs_g, consumed_fats_g) VALUES (?, ?, ?, ?, ?, ?)`,
      [userId, date, updatedTotals.calories, updatedTotals.protein, updatedTotals.carbs, updatedTotals.fats]
    );
  }

  const response = {
    calories: buildMacroResponse(updatedTotals.calories, user.target_calories),
    protein: buildMacroResponse(updatedTotals.protein, user.target_protein_g),
    carbs: buildMacroResponse(updatedTotals.carbs, user.target_carbs_g),
    fats: buildMacroResponse(updatedTotals.fats, user.target_fats_g),
  };

  const previousResponse = {
    calories: buildMacroResponse(previousTotals.calories, user.target_calories),
    protein: buildMacroResponse(previousTotals.protein, user.target_protein_g),
    carbs: buildMacroResponse(previousTotals.carbs, user.target_carbs_g),
    fats: buildMacroResponse(previousTotals.fats, user.target_fats_g),
  };

  const newAlerts = Object.keys(response).reduce((alerts, macroKey) => {
    const previousTierRank = getTierRank(previousResponse[macroKey].tier);
    const currentTierRank = getTierRank(response[macroKey].tier);

    if (currentTierRank > previousTierRank) {
      const over = response[macroKey].consumed - user[`target_${macroKey}${macroKey === 'calories' ? '' : '_g'}`];
      let message;

      if (response[macroKey].tier === 'red') {
        message = over > 0
          ? `⚠️ ${macroKey.charAt(0).toUpperCase() + macroKey.slice(1)} exceeded by ${over}${macroKey === 'calories' ? ' kcal' : 'g'} after your last order.`
          : `⚠️ ${macroKey.charAt(0).toUpperCase() + macroKey.slice(1)} is exactly at your daily target after your last order.`;
      } else {
        message = `You're at ${response[macroKey].percent}% of your daily ${macroKey} target`;
      }

      alerts.push({
        macro: macroKey,
        percent: response[macroKey].percent,
        tier: response[macroKey].tier,
        message,
      });
    }

    return alerts;
  }, []);

  return res.json({ totals: response, new_alerts: newAlerts });
}

async function resetDailyLog(req, res) {
  const { user_id } = req.body;
  const userId = Number(user_id);

  if (!userId) {
    return res.status(400).json({ error: 'user_id is required and must be a number' });
  }

  const user = await get('SELECT * FROM Users WHERE user_id = ?', [userId]);
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }

  const date = new Date().toISOString().slice(0, 10);
  const existingLog = await get('SELECT * FROM Daily_Logs WHERE user_id = ? AND date = ?', [userId, date]);

  if (existingLog) {
    await run(
      `UPDATE Daily_Logs SET consumed_calories = 0, consumed_protein_g = 0, consumed_carbs_g = 0, consumed_fats_g = 0 WHERE log_id = ?`,
      [existingLog.log_id]
    );
  } else {
    await run(
      `INSERT INTO Daily_Logs (user_id, date, consumed_calories, consumed_protein_g, consumed_carbs_g, consumed_fats_g) VALUES (?, ?, 0, 0, 0, 0)`,
      [userId, date]
    );
  }

  return res.json({ message: 'Daily log reset for today' });
}

module.exports = {
  calculateMacroAlertStatus,
  getDailyLog,
  getDailyLogHistory,
  completeOrder,
  resetDailyLog,
};
