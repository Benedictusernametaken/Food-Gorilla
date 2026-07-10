const request = require('supertest');
const fs = require('fs');
const path = require('path');

const TEST_DB = path.join(__dirname, '..', 'data', 'test.db');
process.env.SQLITE_DB = TEST_DB;
if (fs.existsSync(TEST_DB)) fs.unlinkSync(TEST_DB);

const { run, db, initDb } = require('../config/db');
const app = require('../app');
const { calculateMacroAlertStatus } = require('../controllers/dailyLogController');

beforeAll(async () => {
  await initDb();
});

afterAll(() => {
  db.close();
  if (fs.existsSync(TEST_DB)) fs.unlinkSync(TEST_DB);
});

describe('calculateMacroAlertStatus', () => {
  test('returns green below 75%', () => {
    expect(calculateMacroAlertStatus(74, 100)).toBe('green');
  });

  test('returns yellow at 75%', () => {
    expect(calculateMacroAlertStatus(75, 100)).toBe('yellow');
  });

  test('returns yellow at 99%', () => {
    expect(calculateMacroAlertStatus(99, 100)).toBe('yellow');
  });

  test('returns red at 100%', () => {
    expect(calculateMacroAlertStatus(100, 100)).toBe('red');
  });
});

describe('/api/orders/complete', () => {
  test('upserts daily log and accumulates totals for same day', async () => {
    const today = new Date().toISOString().slice(0, 10);
    const firstResponse = await request(app)
      .post('/api/orders/complete')
      .send({ user_id: 1, calories: 200, protein_g: 20, carbs_g: 30, fats_g: 10 });

    expect(firstResponse.status).toBe(200);
    expect(firstResponse.body.totals.calories.consumed).toBe(1400);

    const secondResponse = await request(app)
      .post('/api/orders/complete')
      .send({ user_id: 1, calories: 300, protein_g: 25, carbs_g: 40, fats_g: 5 });

    expect(secondResponse.status).toBe(200);
    expect(secondResponse.body.totals.calories.consumed).toBe(1700);
    expect(secondResponse.body.totals.protein.consumed).toBe(125);
    expect(secondResponse.body.totals.carbs.consumed).toBe(230);
    expect(secondResponse.body.totals.fats.consumed).toBe(60);

    const dashboardResponse = await request(app)
      .get('/api/daily-log')
      .query({ user_id: 1, date: today });

    expect(dashboardResponse.status).toBe(200);
    expect(dashboardResponse.body.calories.consumed).toBe(1700);
  });

  test('returns new_alerts only on tier crossing', async () => {
    const today = new Date().toISOString().slice(0, 10);
    await request(app)
      .post('/api/orders/complete')
      .send({ user_id: 2, calories: 1200, protein_g: 60, carbs_g: 80, fats_g: 20 });

    const crossingResponse = await request(app)
      .post('/api/orders/complete')
      .send({ user_id: 2, calories: 200, protein_g: 10, carbs_g: 10, fats_g: 5 });

    expect(crossingResponse.status).toBe(200);
    expect(crossingResponse.body.new_alerts.length).toBeGreaterThanOrEqual(1);

    const sameTierResponse = await request(app)
      .post('/api/orders/complete')
      .send({ user_id: 2, calories: 10, protein_g: 1, carbs_g: 2, fats_g: 1 });

    expect(sameTierResponse.status).toBe(200);
    expect(sameTierResponse.body.new_alerts.length).toBe(0);
  });

  test('adds exactly the submitted values on each call for the same day', async () => {
    const input = { user_id: 1, calories: 450, protein_g: 30, carbs_g: 55, fats_g: 12 };

    await request(app).post('/api/daily-log/reset').send({ user_id: 1 });

    for (let i = 0; i < 3; i += 1) {
      const response = await request(app).post('/api/orders/complete').send(input);
      expect(response.status).toBe(200);
    }

    const finalResponse = await request(app)
      .get('/api/daily-log')
      .query({ user_id: 1, date: new Date().toISOString().slice(0, 10) });

    expect(finalResponse.status).toBe(200);
    expect(finalResponse.body.calories.consumed).toBe(450 * 3);
    expect(finalResponse.body.protein.consumed).toBe(30 * 3);
    expect(finalResponse.body.carbs.consumed).toBe(55 * 3);
    expect(finalResponse.body.fats.consumed).toBe(12 * 3);
  });

  test('single simulate order adds exactly one input amount after reset', async () => {
    const input = { user_id: 1, calories: 450, protein_g: 30, carbs_g: 55, fats_g: 12 };

    await request(app).post('/api/daily-log/reset').send({ user_id: 1 });
    const response = await request(app).post('/api/orders/complete').send(input);
    expect(response.status).toBe(200);
    expect(response.body.totals.calories.consumed).toBe(450);
    expect(response.body.totals.protein.consumed).toBe(30);
    expect(response.body.totals.carbs.consumed).toBe(55);
    expect(response.body.totals.fats.consumed).toBe(12);

    const finalResponse = await request(app)
      .get('/api/daily-log')
      .query({ user_id: 1, date: new Date().toISOString().slice(0, 10) });

    expect(finalResponse.status).toBe(200);
    expect(finalResponse.body.calories.consumed).toBe(450);
    expect(finalResponse.body.protein.consumed).toBe(30);
    expect(finalResponse.body.carbs.consumed).toBe(55);
    expect(finalResponse.body.fats.consumed).toBe(12);
  });

  test('exact target order alert wording does not say exceeded by 0', async () => {
    await request(app).post('/api/daily-log/reset').send({ user_id: 1 });

    const response = await request(app)
      .post('/api/orders/complete')
      .send({ user_id: 1, calories: 2200, protein_g: 150, carbs_g: 250, fats_g: 70 });

    expect(response.status).toBe(200);
    expect(response.body.new_alerts.length).toBeGreaterThanOrEqual(1);
    response.body.new_alerts.forEach((alert) => {
      expect(alert.message).not.toContain('exceeded by 0');
    });
    expect(response.body.new_alerts.some((alert) => alert.message.includes('is exactly at your daily target'))).toBe(true);
  });

  test('reset today\'s log zeros out dashboard totals', async () => {
    await request(app).post('/api/daily-log/reset').send({ user_id: 1 });

    const finalResponse = await request(app)
      .get('/api/daily-log')
      .query({ user_id: 1, date: new Date().toISOString().slice(0, 10) });

    expect(finalResponse.status).toBe(200);
    expect(finalResponse.body.calories.consumed).toBe(0);
    expect(finalResponse.body.protein.consumed).toBe(0);
    expect(finalResponse.body.carbs.consumed).toBe(0);
    expect(finalResponse.body.fats.consumed).toBe(0);
  });

  test('returns 7-day history with zeroed days when missing', async () => {
    const historyResponse = await request(app)
      .get('/api/daily-log/history')
      .query({ user_id: 2, days: 7 });

    expect(historyResponse.status).toBe(200);
    expect(Array.isArray(historyResponse.body)).toBe(true);
    expect(historyResponse.body).toHaveLength(7);

    const today = new Date().toISOString().slice(0, 10);
    expect(historyResponse.body[6].date).toBe(today);
    expect(historyResponse.body[6].consumed_calories).toBeGreaterThanOrEqual(0);

    const zeroDays = historyResponse.body.slice(0, 6).filter((entry) => entry.consumed_calories === 0);
    expect(zeroDays.length).toBeGreaterThanOrEqual(5);
  });
});
