const fs = require('fs');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();

const dbFile = process.env.SQLITE_DB || path.join(__dirname, '..', 'data', 'nutritrack.db');
const dataDir = path.dirname(dbFile);
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

const db = new sqlite3.Database(dbFile);

function formatDate(date) {
  return date.toISOString().slice(0, 10);
}

function run(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.run(sql, params, function (err) {
      if (err) {
        reject(err);
      } else {
        resolve(this);
      }
    });
  });
}

function get(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.get(sql, params, (err, row) => {
      if (err) {
        reject(err);
      } else {
        resolve(row);
      }
    });
  });
}

function all(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => {
      if (err) {
        reject(err);
      } else {
        resolve(rows);
      }
    });
  });
}

async function initDb() {
  await run('PRAGMA foreign_keys = ON');
  await run(`CREATE TABLE IF NOT EXISTS Users (
    user_id INTEGER PRIMARY KEY,
    target_calories INTEGER NOT NULL,
    target_protein_g INTEGER NOT NULL,
    target_carbs_g INTEGER NOT NULL,
    target_fats_g INTEGER NOT NULL
  )`);

  await run(`CREATE TABLE IF NOT EXISTS Daily_Logs (
    log_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    consumed_calories INTEGER NOT NULL DEFAULT 0,
    consumed_protein_g INTEGER NOT NULL DEFAULT 0,
    consumed_carbs_g INTEGER NOT NULL DEFAULT 0,
    consumed_fats_g INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    UNIQUE(user_id, date)
  )`);

  await run(
    `INSERT OR IGNORE INTO Users (user_id, target_calories, target_protein_g, target_carbs_g, target_fats_g)
     VALUES (1, 2200, 150, 250, 70),
            (2, 2000, 130, 220, 60)`
  );

  const today = new Date().toISOString().slice(0, 10);
  await run(
    `INSERT OR IGNORE INTO Daily_Logs (log_id, user_id, date, consumed_calories, consumed_protein_g, consumed_carbs_g, consumed_fats_g)
     VALUES (1, 1, ?, 1200, 80, 160, 45),
            (2, 2, ?, 900, 70, 120, 35)`,
    [today, today]
  );

  const sampleHistory = [
    { offset: -6, calories: 1900, protein: 140, carbs: 220, fats: 60 },
    { offset: -5, calories: 2050, protein: 145, carbs: 230, fats: 65 },
    { offset: -4, calories: 2250, protein: 155, carbs: 240, fats: 75 },
    { offset: -3, calories: 2100, protein: 150, carbs: 235, fats: 70 },
    { offset: -2, calories: 2000, protein: 135, carbs: 215, fats: 55 },
    { offset: -1, calories: 1800, protein: 130, carbs: 205, fats: 50 },
  ];

  for (const entry of sampleHistory) {
    const date = new Date();
    date.setDate(date.getDate() + entry.offset);
    await run(
      `INSERT OR IGNORE INTO Daily_Logs (user_id, date, consumed_calories, consumed_protein_g, consumed_carbs_g, consumed_fats_g)
       VALUES (?, ?, ?, ?, ?, ?)`,
      [1, formatDate(date), entry.calories, entry.protein, entry.carbs, entry.fats]
    );
  }
}

module.exports = {
  db,
  run,
  get,
  all,
  initDb,
};
