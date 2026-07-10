# Daily-Fitness-Tracking-Dashboard-

This repository contains a self-contained NutriTrack daily nutrition dashboard module.
It includes a minimal SQLite-backed backend, an order completion hook, a dashboard API, tiered macro alert logic, and a development-only simulation UI.

## API Endpoints

### `POST /api/orders/complete`

Request body:

```json
{
  "user_id": 1,
  "calories": 450,
  "protein_g": 30,
  "carbs_g": 55,
  "fats_g": 12
}
```

Behavior:

- Upserts today's `Daily_Logs` row for the user
- Adds the completed order macros to existing totals
- Returns updated totals and any newly crossed macro alerts

Example response:

```json
{
  "totals": {
    "calories": {"consumed": 1650, "target": 2200, "percent": 75, "tier": "yellow"},
    "protein": {"consumed": 110, "target": 150, "percent": 73, "tier": "green"},
    "carbs": {"consumed": 210, "target": 250, "percent": 84, "tier": "yellow"},
    "fats": {"consumed": 55, "target": 70, "percent": 79, "tier": "yellow"}
  },
  "new_alerts": [
    {"macro": "calories", "percent": 75, "tier": "yellow", "message": "You're at 75% of your daily calories target"}
  ]
}
```

### `GET /api/daily-log?user_id=<id>&date=<YYYY-MM-DD>`

Returns current consumed totals, targets, percent of target, and tier for each macro.

Example response:

```json
{
  "calories": {"consumed": 1800, "target": 2200, "percent": 82, "tier": "yellow"},
  "protein": {"consumed": 140, "target": 150, "percent": 93, "tier": "yellow"},
  "carbs": {"consumed": 200, "target": 250, "percent": 80, "tier": "yellow"},
  "fats": {"consumed": 60, "target": 70, "percent": 86, "tier": "yellow"}
}
```

## Run locally

Install dependencies:

```bash
npm install
```

Start the app:

```bash
npm start
```

Open `http://localhost:3000` in a browser to view the dashboard and simulate orders.
