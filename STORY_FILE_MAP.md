# Story → File Map (Presentation Reference)

Quick reference for "which files built this story" and how those files
talk to each other. Not a code walkthrough — just enough to point at a
file on screen and explain its role.

## How the tiers always connect

```
Browser  →  Frontend (Express, frontend/*.js)  →  Backend (Flask, backend/app/*.py)  →  Postgres
         (renders HTML, holds session cookie)   (does the real work, owns the DB)
```

- The **browser never talks to the backend directly** — every frontend
  route handler makes its own server-side `fetch()` to
  `http://backend:5000`. This is why you won't see backend URLs in any
  client-side `<script>`.
- **Auth is a signed JWT**, not a server session. `POST /auth/login` or
  `/vendor/auth/register` returns a token; the frontend stores it as an
  `httpOnly` cookie (`fg_token` for customers, `fg_vendor_token` for
  vendors — two separate cookies so a browser can't mix up sessions).
  Every subsequent frontend page reads that cookie and forwards it to
  the backend as `Authorization: Bearer <token>`; the backend decodes
  and trusts it, never the frontend.
- Each story's backend file and frontend file is **one pair, wired in
  by exactly one line each** (`import app.<feature>` in
  `backend/app/__init__.py`, `app.use(require('./<feature>'))` in
  `frontend/index.js`). No shared helper modules — each file owns its
  own DB queries and auth checks. This was a deliberate choice to avoid
  merge conflicts across the team.

## Story → files

### Story 7 — User Authentication (Sign Up & Login)
| Layer | File | Role |
|---|---|---|
| Backend | `backend/app/auth.py` | `/auth/register`, `/auth/login`, `/auth/reset-request`, `/auth/reset-confirm`. Issues the `fg_token` JWT. |
| Frontend | `frontend/auth.js` | `/login`, `/signup`, `/profile`, `/logout`, `/reset-request`, `/reset-confirm` pages. Sets/reads the `fg_token` cookie. |
| DB | `users` table | |

`/profile` is the hub page — its button row links out to Stories 1, 4, 6, 10.

### Story 8 — Vendor Account Management
| Layer | File | Role |
|---|---|---|
| Backend | `backend/app/vendor_auth.py` | `/vendor/auth/register`, `/vendor/auth/login`. Issues the `fg_vendor_token` JWT. |
| Frontend | `frontend/vendor_auth.js` | `/vendor/login`, `/vendor/signup`, `/vendor/portal`, `/vendor/logout`. |
| DB | `vendors` table | |

Mirrors Story 7's pattern exactly, but kept on a separate cookie/token
so customer and vendor sessions never collide.

### Story 5 — Vendor Management Portal
| Layer | File | Role |
|---|---|---|
| Backend | `backend/app/vendor_meals.py` | CRUD on a vendor's own meals: list/create/get/update/delete, plus an availability toggle. |
| Frontend | `frontend/vendor_meals.js` | `/vendor/meals` (list + create) and `/vendor/meals/:id/edit`. |
| DB | `meals`, `ingredients`, `meal_ingredients` | |

Requires a valid `fg_vendor_token` (Story 8) and is what actually
populates the `meals` table that Stories 2/3 read from.

### Story 1 — User Profile & Macro Calculator
| Layer | File | Role |
|---|---|---|
| Backend | `backend/app/macro_profile.py` | Calculates BMR/TDEE-based targets from age/weight/height/goal; saves/lists/deletes profiles. |
| Frontend | `frontend/macro_calculator.js` | `/macros` — calculator form + saved-profile list. |
| DB | `macro_profiles` table | |

Requires `fg_token` (Story 7). The saved target here is what Story 4's
dashboard compares actual intake against.

### Story 2 — Smart Metric-Filtered Menu
| Layer | File | Role |
|---|---|---|
| Backend | `backend/app/menu.py` | `/menu` — lists all available meals with macros, grouped by vendor. |
| Frontend | `frontend/menu.js` | `/` (the homepage) — renders meal cards and client-side range-slider filters (calories/protein/carbs/fats), no reload needed to filter. |
| DB | `meals`, `vendors` | |

The homepage is also the public entry point: it reads the `fg_token`
cookie (if present) to swap the "Log In" button for a "`<username>`'s
Profile" / "Log Out" pair, and links out to Story 3 (per meal),
Story 10 (cart), and Story 8 (vendor portal).

### Story 3 — Interactive Meal-Builder / CRUD
| Layer | File | Role |
|---|---|---|
| Backend | `backend/app/meal_builder.py` | `GET /meals/:id/customize` (ingredient options + defaults), `POST /meals/:id/customize` (validates an override map and recomputes price/macros). |
| Frontend | `frontend/meal_builder.js` | `/meals/:id/customize` — per-ingredient +/− quantity controls, live-recalculates totals client-side, then hands off to Story 10's cart endpoint. |
| DB | `meal_ingredients`, `ingredients` | |

This page doesn't persist anything itself — "Add to Cart" is a
client-side `fetch('/cart/items', ...)` call into Story 10's endpoint.

### Story 10 — Cart Management
| Layer | File | Role |
|---|---|---|
| Backend | `backend/app/cart.py` | `GET/DELETE /cart`, `POST /cart/items`, `PUT/DELETE /cart/items/:id`. A cart *is* an `orders` row stuck at `order_status = 'pending'` — no separate cart table. |
| Frontend | `frontend/cart.js` | `/cart` — item list, quantity update, remove, clear-cart, links to checkout. Also hosts the `/cart/items` proxy that Story 3's "Add to Cart" button calls. |
| DB | `orders`, `order_items`, `order_item_ingredients` | |

### Story 9 — Order and Checkout System
| Layer | File | Role |
|---|---|---|
| Backend | `backend/app/checkout.py` | `POST /checkout` flips the pending order to `confirmed` and writes today's macros into `daily_logs` (this is the Story 9 ↔ Story 11 link). Also `GET /orders`, `GET /orders/:id`. |
| Frontend | `frontend/checkout.js` | `/checkout` — read-only order review pulled from the same cart data, "Place Order" button, confirmation screen. |
| DB | `orders`, `daily_logs` | |

Checkout only ever acts on whatever cart (Story 10) currently exists
for the logged-in user — there's no order data entered here directly.

### Story 11 — Daily Log Tracking
| Layer | File | Role |
|---|---|---|
| Backend | `backend/app/daily_log.py` | `GET /daily-log`, `GET /daily-log/history` — read-side API over the `daily_logs` table. |
| Frontend | *(none dedicated)* | No standalone page calls this yet — the *write* side happens inside Story 9's `checkout.py` (every confirmed order adds to today's row), and the one place today's totals are actually shown to a user is Story 4's dashboard, which queries `daily_logs` directly rather than through this file. |
| DB | `daily_logs` table | |

Worth flagging in the presentation: the log is being written and read
correctly end-to-end, just not through this file's own GET routes yet —
a gap if a future "log history" page is wanted.

### Story 4 — Daily Fitness Tracking Dashboard
| Layer | File | Role |
|---|---|---|
| Backend | `backend/app/dashboard.py` | `GET /dashboard` — joins today's `daily_logs` row against the user's saved `macro_profiles` target and flags any macro that's been exceeded. |
| Frontend | `frontend/dashboard.js` | `/dashboard` — progress bars per macro, red/over-target state. Shows a "set your targets" prompt (→ Story 1) if no profile exists yet. |
| DB | `daily_logs`, `macro_profiles` | |

This is the one page that visibly ties Story 1 (target), Story 9
(what got logged), and Story 11 (the log table) together.

### Story 6 — Scheduled Subscription Engine
| Layer | File | Role |
|---|---|---|
| Backend | `backend/app/subscriptions.py` | Create/list/get a weekly meal plan, modify/cancel individual scheduled slots, with day-of-week/time-slot occurrence math. |
| Frontend | `frontend/subscriptions.js` | `/subscriptions` — weekly schedule view and edit UI. |
| DB | `subscriptions`, `subscription_schedule` | |

Independent of the cart/checkout/order flow — it schedules meals
against a day/time slot rather than an immediate `orders` row.

## One-page cheat sheet

| # | Story | Backend file | Frontend file |
|---|---|---|---|
| 7 | Customer Auth | `auth.py` | `auth.js` |
| 8 | Vendor Auth | `vendor_auth.py` | `vendor_auth.js` |
| 5 | Vendor Portal | `vendor_meals.py` | `vendor_meals.js` |
| 1 | Macro Calculator | `macro_profile.py` | `macro_calculator.js` |
| 2 | Menu Search | `menu.py` | `menu.js` |
| 3 | Meal Builder | `meal_builder.py` | `meal_builder.js` |
| 10 | Cart | `cart.py` | `cart.js` |
| 9 | Checkout | `checkout.py` | `checkout.js` |
| 11 | Daily Log | `daily_log.py` | *(none — see above)* |
| 4 | Dashboard | `dashboard.py` | `dashboard.js` |
| 6 | Subscriptions | `subscriptions.py` | `subscriptions.js` |

Every backend file also has a matching `backend/tests/test_<file>.py`
(pytest, route-level: valid input → expected shape, invalid input →
sensible error).
