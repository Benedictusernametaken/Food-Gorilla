# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Food Gorilla — a 3-tier meal-marketplace app. Node/Express server-rendered frontend, Flask JSON API backend, Postgres database, all wired together with Docker Compose and deployed via a Jenkins pipeline.

## Running the stack

```bash
# Local dev with live-reload bind mounts (frontend code changes reflected without rebuild)
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.dev.yml up

# Plain production-style run (auto-merges docker-compose.override.yml for host ports)
docker compose up
```

Requires `POSTGRES_PASSWORD` in the environment (see `.env.example`). `docker-compose.override.yml` is auto-merged by Compose whenever invoked without explicit `-f` flags and adds host port bindings (frontend 3000, backend 5000, database 5432); `docker-compose.dev.yml` is opt-in only and is never auto-merged. **Never add bind mounts to `docker-compose.override.yml`** — Jenkins' production deploy runs plain `docker compose up` via Docker-outside-of-Docker, and a relative bind-mount path there would resolve against Jenkins' own container filesystem, silently mounting an empty directory over `/app`.

Services: `frontend` (Express, port 3000) → `backend` (Flask, port 5000) → `database` (Postgres 15, port 5432), plus a `jenkins` service for CI/CD (port 8080). `docker-compose.yml` never sets a top-level `name:`, so always pass `-p foodgorilla` (or `-p foodgorilla_test`) explicitly when running Compose commands standalone — otherwise the project name is derived from the invoking directory, which is unpredictable under Jenkins.

There is no test suite, linter, or build step configured in this repo currently.

## Backend (Flask)

- Single-file app: `backend/app/main.py`, with `app = Flask(__name__)` created once in `backend/app/__init__.py` and imported back in `main.py` (`from app import app`) rather than a factory pattern.
- Run directly: `flask --app app.main run --host=0.0.0.0 --port=5000` (needs `DATABASE_URL` and `PYTHONPATH=/app` set — see `docker-compose.yml` for the exact env).
- `get_db()` opens a fresh `psycopg2` connection per request and reads `DATABASE_URL` from the environment with no fallback — it fails loudly rather than silently defaulting. Every route follows the same `try/finally: conn.close()` pattern; there's no connection pooling.
- Vendor auth is **opaque bearer tokens**, not JWTs: `POST /api/auth/login` issues a random token stored in the `vendor_sessions` table with a 24h TTL, and logout just deletes the row. This makes server-side revocation trivial (no signing-key rotation needed). The `@require_vendor_auth` decorator checks the `vendor_sessions` table and stashes `g.vendor_id` for handlers.
- All vendor-scoped queries filter by `vendor_id` in the `WHERE` clause (never trust `meal_id` alone) — follow this pattern for any new vendor-owned resource.
- `GET /api/meals/search` (public marketplace search) only ever returns `is_available = TRUE` meals; range filters (`min_price`/`max_price`, `min_calories`/`max_calories`, etc.) map through the hardcoded `SEARCH_RANGE_FIELDS` dict so query-param keys are never interpolated directly into SQL — only their looked-up column names are, and those come from a fixed dict, not user input.
- Health check (`/health-check`) does a real `SELECT 1` against the DB, not just a liveness check — this is what both the Docker `HEALTHCHECK` and the Jenkins/Ansible smoke tests key off of via the `database_connectivity` field.

## Frontend (Express)

- `frontend/index.js` is the entrypoint; routers live in `frontend/routes/` (`marketplace.js`, `auth.js`, `dashboard.js`) and are mounted in that order.
- The frontend is a **server-rendered proxy in front of the Flask API**, not a SPA. Pages are built with the `pageShell()` helper (`frontend/views/layout.js`) returning raw HTML template strings — no templating engine or frontend framework. Client-side interactivity lives in plain JS files under `frontend/public/` (`dashboard.js`, `marketplace.js`), loaded via `extraScripts`.
- `frontend/lib/backend.js` (`backendRequest`) makes server-to-server calls to Flask over the Docker network (`BACKEND_URL`, defaults to `http://backend:5000`) — no CORS handling needed since browser JS never talks to Flask directly.
- Vendor auth session: the Flask bearer token is stored in an **httpOnly cookie** (`vendor_token`, see `frontend/lib/auth.js`) so browser JS can never read it. Browser JS calls same-origin `/api/dashboard/*` routes, which read the cookie server-side and forward it as an `Authorization: Bearer` header to Flask. `requireLoginPage`/`requireLoginApi` middleware gate page vs. JSON routes respectively.
- When adding a new vendor-authenticated feature, follow the existing proxy pattern: add the real route to `backend/app/main.py` behind `@require_vendor_auth`, then add a thin `/api/dashboard/...` proxy route in `frontend/routes/dashboard.js` that forwards `req.vendorToken`.

## Database

- Single schema file: `database/init.sql`, applied automatically by the official Postgres image via `/docker-entrypoint-initdb.d/`. It unconditionally `DROP TABLE ... CASCADE`s everything first, then recreates the full schema and inserts demo seed data — it is a full reset script, not a migration.
- Demo login seeded: `owner@leanmean.com` / `password123`.
- Seed inserts use subqueries to look up FK IDs by name (never hardcoded `SERIAL` IDs or `setval()`), so the seed data is order-independent.
- Schema is organized around numbered "Features" via SQL comments (e.g. `-- Feature 2: Smart Nutritional Search & Filter`, `-- Feature 5: Vendor Nutritional Portal`) — several tables (`macro_profiles`, `ingredients`, `daily_logs`, `subscriptions`, `subscription_schedule`) exist in the schema for planned features not yet implemented in `backend/app/main.py`.
- `order_items` and `order_item_ingredients` snapshot price/macro values at order time rather than joining live against `meals`/`meal_ingredients`, so edits to a meal's recipe never retroactively change past orders.

## CI/CD (Jenkins + Ansible)

- `Jenkinsfile` defines a Multibranch Pipeline. Branch discovery/polling is configured at the Jenkins job level (not via `pollSCM` in the Jenkinsfile).
- Stage order: preflight checks (Ansible, all branches) → integration testing (isolated Compose stack under `-p foodgorilla_test`, all branches) → auto-open PR to `main` (only on `feature/*` branches, only after tests pass) → deploy to production (only on `main`) → post-deploy smoke test (Ansible, only on `main`).
- Integration testing always runs with `-p ${APP_NAME}_test` and `-f docker-compose.yml` only (no override file), so it never claims production host ports and can run alongside a live prod stack.
- Production deploy (`Deploy to Production` stage) explicitly lists services (`database frontend backend`) on every `docker compose` command and uses `stop`/`rm` rather than `down` — an unscoped `docker compose down -p foodgorilla` would tear down the *entire* named project, including the `jenkins` service itself, since Jenkins runs inside that same Compose project via a mounted `docker.sock`.
- `ansible/playbook.yml` has two tag-selected plays sharing one file: `--tags preflight` (host readiness: Docker/Compose/disk, before any build) and `--tags smoke_test` (post-deploy verification: waits for backend/frontend ports, asserts `/health-check` reports `database_connectivity == "CONNECTED"`, asserts frontend HTML contains "Food Gorilla"). Both target `localhost` directly since Ansible itself runs inside the Jenkins container.
