# Food Gorilla — Project Memory

## What this is
A macro-tracking food delivery app. Every menu item is tagged with
calories/protein/carbs/fats so users can order meals that fit their daily
nutrition targets. 3-tier architecture: PostgreSQL database, Flask
backend, Express/Node frontend, all orchestrated with Docker Compose and
a Jenkins CI/CD pipeline.

The full spec is **`PRODUCT_BACKLOG.md`** (root of the repo) — read it in
full before starting any story. It contains the complete User Story, CoS
(Conditions of Satisfaction), and Acceptance Criteria for all 11 stories.
The one-line list below is just a quick index, not a substitute:
macro calculator/profile, filtered menu search, meal-builder CRUD, daily
dashboard, vendor portal, subscriptions, customer auth, vendor auth,
checkout, cart, daily nutrition log.

`PRODUCT_BACKLOG.md` is the source of truth for what "done" means for
each story — treat its Acceptance Criteria as the actual spec to satisfy,
not assumptions about what a generic delivery app would need. One known
issue in the original document: Story 9's CoS/Acceptance Criteria text is
a copy-paste of Story 7's (login/auth), not actually about checkout —
build Story 9 based on its User Story title and general checkout logic,
not its literal (wrong) CoS text.

## Architecture
- `database/` — Postgres 15, schema in `init.sql`. Tables already cover
  all 11 stories: `users`, `macro_profiles`, `vendors`, `meals`,
  `ingredients`, `meal_ingredients`, `orders`, `order_items`,
  `order_item_ingredients`, `daily_logs`, `subscriptions`,
  `subscription_schedule`. **Treat this schema as final** — extend it,
  don't redesign it, unless a story genuinely can't be satisfied by it.
- `backend/` — Flask. Entry point `app/main.py` (do not add new routes
  here — see Conventions below).
- `frontend/` — Express/Node. Entry point `index.js` (same rule — don't
  add new pages here directly).
- Services talk to each other by **Docker service name**, never
  `127.0.0.1` or `localhost` — e.g. backend reaches Postgres at
  `database:5432`, frontend reaches backend at `http://backend:5000`.
  `DATABASE_URL` and `BACKEND_URL` are already wired via
  `docker-compose.yml`; read them from `os.environ`/`process.env`, never
  hardcode connection strings.
- Frontend calls the backend **server-side** (inside Express route
  handlers), not from client-side JS in the browser. This was a
  deliberate choice to avoid CORS entirely — don't introduce
  client-side `fetch` calls to the backend without discussing it first.

## Conventions — how to add a new feature
Every new feature/route must be self-contained to avoid merge conflicts
across a 6-person team all working in this repo simultaneously:
- **Backend:** one new file per feature, e.g. `backend/app/<feature>.py`.
  Import the shared `app` object (`from app import app`) and define
  routes directly on it — same pattern as `main.py`'s own routes. Wire it
  in with exactly one line in `backend/app/__init__.py`:
  `import app.<feature>  # noqa: F401`. Nothing else in `__init__.py` or
  `main.py` should change.
- **Frontend:** one new file per page, e.g. `frontend/<feature>.js`,
  exporting an `express.Router()`. Wiring it into `index.js` needs
  `require('./<feature>')` + `app.use(router)` — but only do this once
  the file causing that shared edit (usually the homepage owner's
  `index.js` work) is stable/merged, not while it's actively changing.
- Don't add a shared helper module (e.g. a `db.py` connection wrapper)
  unless asked — keep each feature file's dependencies to itself + the
  shared `app` instance + the database. Simpler and lower-conflict beats
  DRY here.
## Auth — build this first, not last
Story 7 (customer auth) and Story 8 (vendor auth) are **required stories
in the backlog, not optional or out of scope.** They should be built
like every other story — nothing here means skip them.

Prioritize building Story 7/8 **before** most other stories: cart,
checkout, dashboard, daily log, and subscriptions all need to know which
user they're acting on, so they can't be genuinely finished until real
auth exists.

Until Story 7/8 is built: any other route needing a user may accept
`user_id` as a query param as a stopgap, clearly commented as
`# TEMPORARY until Story 7/8 auth exists` (or the JS equivalent), so
it's easy to find and replace — not left as permanent behavior.

## Design reference — visual/structural only, not behavioral
`design-reference/style.css` and `design-reference/auth.html` are real
design files, but scoped narrowly:
- **Use them for:** layout structure, CSS classes, spacing, colors, the
  overall visual identity (warm peach/orange gradient, pill-shaped
  buttons, food emoji accents). When building Story 7/8's login/signup
  pages, match this structure — don't invent a different div layout that
  happens to reuse the same class names.
- **Do NOT use them for:** the marketing copy (rewrite all headline/body
  text to match Food Gorilla's actual identity — a consumer macro/
  nutrition-tracking food delivery app — not the mismatched "food
  production/supply chain" wording in the mockup), or the `<script>`
  behavior (any embedded fetch calls, endpoint names, or session
  mechanism in the original mockup were a discarded prototype — design
  the real API contract for Story 7/8 independently; nothing here is a
  mandated spec).
- Branding: use **"Food Gorilla"** (with a space) consistently — the
  mockup's "FoodGorilla" (no space) is not the correct name.
- `.macro-grid`/`.macro-card`/`.advice-box`/`fieldset`/`legend` classes in
  the CSS are intended for Story 1's calculator input + results page,
  even though no matching mockup HTML exists yet — same rule applies
  when that page gets built.

## Scope additions beyond the 11-story backlog
- **Password reset** is in scope — build it as part of Story 7 (customer
  auth), even though it isn't a numbered backlog story.
- **Admin login is explicitly out of scope** — it's not a role in the
  schema or backlog. If adapting `design-reference/auth.html`'s
  structure, drop the "admin login" link entirely rather than building
  a third auth role.


## Testing
Backend tests use **pytest**. Every story that adds backend routes needs
basic route-level tests as part of that same PR — not a follow-up task.
At minimum: does the route return the expected shape on valid input, and
a sensible error on invalid input (missing params, no matching record,
etc). The pipeline currently only verifies infra health (containers
build, database connects) — it does not check feature correctness, so
these tests are the only thing that will actually catch a broken route
before it merges.

## Branch/PR workflow
One `feature/*` branch per story (or a tightly-coupled small group, e.g.
cart + checkout if genuinely inseparable) — not one large branch for
multiple unrelated stories. Each branch should be pushed and go through
Integration Testing individually, with its own PR, before starting the
next story. Build foundational stories (auth) first so later stories
build on something already merged and verified, not something still in
flight. This is slower than batching everything into one big branch, but
matches the CI/CD pipeline this project already has — use it as
designed rather than working around it.

## Build order
Numeric story order in the backlog is NOT the build order — dependencies
matter more. Build in this sequence:

**7, 8 → 5 → 1 → 2 → 3 → 10 → 9 → 11 → 4 → 6**

Reasoning:
- 7/8 (auth) first — everything else needs a real user to act on.
- 5 (vendor portal) next — creates real meals/vendor data; building
  browsing/customization against only `init.sql` seed data would mean
  redoing it once real vendor data exists.
- 1 (macro profile) — independent of everything except auth, fits
  anywhere after 7/8. Placed here as a natural break before the
  order-flow chain starts.
- 2 (menu search) → 3 (meal-builder) — need real meal data from 5.
- 10 (cart) — needs a customized meal object from 3.
- 9 (checkout) — needs something in the cart from 10.
- 11 (daily log) — needs a completed order from 9.
- 4 (dashboard) — needs both real logged data (11) and a target to
  compare against (1).
- 6 (subscriptions) last — most complex, sits on top of orders/meals
  already working end-to-end.

**Progress marker** (update this line as stories merge, so a fresh
session or a different Claude Code instance knows where to resume
without being re-told):
`Completed: Story 7, Story 8, Story 5, Story 1. Next: Story 2.`


`docker-compose.yml`, `docker-compose.override.yml`,
`docker-compose.dev.yml`, `Jenkinsfile`, `jenkins/`, `ansible/`,
`.devcontainer/devcontainer.json` took a lot of hard-won debugging to
stabilize. Don't modify these unless specifically asked.

If ever asked to touch Docker Compose commands, the one rule that
matters most: **`docker compose down` cannot be scoped to specific
services — it tears down the entire named project.** Since `jenkins` is
a service in the same `docker-compose.yml` as the app tiers, an
unscoped `down` (or `up`/`down` without `-p foodgorilla` and without
explicit service names) can kill the running Jenkins container mid-build.
Always use `docker compose -p foodgorilla stop <service> && ... rm -f
<service>` for anything touching the app tiers, and always name services
explicitly. Never run a bare `docker compose down` or `up` in this repo.

## Branching
Direct pushes to `main` are blocked by branch protection (PR + approval
+ passing Jenkins status check required). Work on a `feature/*` branch;
pushing it triggers Jenkins automatically and opens a PR on success. This
is enforced at the GitHub level regardless of what gets run locally.