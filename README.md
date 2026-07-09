# Food Gorilla

A macro-tracking food delivery platform — every menu item is categorized by
protein/carbs/fats, letting users order meals that fit their daily
nutrition goals. Built as a 3-tier architecture: PostgreSQL database,
Flask backend, Node/Express frontend.

## Architecture

| Tier | Tech | Container |
|---|---|---|
| Database | PostgreSQL 15 | `database` |
| Backend | Flask (Python 3.10) | `backend` |
| Frontend | Express (Node 18) | `frontend` |
| CI/CD | Jenkins (Multibranch Pipeline) | `jenkins` |

Services communicate over Docker's internal network by service name
(e.g. `backend` reaches the database at `database:5432`, not `127.0.0.1`).

## Running the app locally

Every team member does this — no Jenkins involved.

```bash
git clone https://github.com/Benedictusernametaken/Food-Gorilla.git
cd Food-Gorilla
cp .env.example .env
# edit .env and set a real POSTGRES_PASSWORD

docker compose -p foodgorilla up -d --build database frontend backend
```

Verify it's working:
```bash
curl http://localhost:3000
```
You should see a page confirming the frontend, backend, and database are
all connected.

**Note:** always pass `-p foodgorilla` explicitly with any `docker compose`
command in this repo — the project has no hardcoded name, so omitting it
causes Compose to default to a name derived from your current folder,
which won't match anyone else's setup.

### Stopping / restarting

```bash
docker compose -p foodgorilla stop database frontend backend
docker compose -p foodgorilla start database frontend backend
```

Avoid `docker compose -p foodgorilla down` unless you actually want to
tear the whole project down — it can't be scoped to specific services,
so it affects everything under the project name, Jenkins included if
you're the Jenkins host (see below).

## Contributing (branching & CI)

### Creating a feature branch

Direct pushes to `main` are blocked, so all work starts on a `feature/*`
branch:

```bash
git checkout main
git pull origin main
git checkout -b feature/short-description-of-your-work
```

Naming convention: `feature/<what-you're-building>`, lowercase, hyphens
instead of spaces — e.g. `feature/menu-search-filter`,
`feature/order-history-page`. This matters because the Jenkins
Multibranch job and the auto-PR step both match on the `feature/*`
pattern specifically.

Push it up to trigger CI:
```bash
git push -u origin feature/short-description-of-your-work
```

### What happens after you push

- All work happens on a `feature/*` branch — direct pushes to `main` are
  blocked by branch protection.
- Pushing to a `feature/*` branch automatically triggers the Jenkins
  pipeline (build + Integration Testing).
- If the pipeline passes, a pull request into `main` is opened
  automatically.
- Merging into `main` requires an approving review and a passing status
  check, and triggers the full deploy + Ansible verification pipeline.

You don't need to run Jenkins yourself to contribute — just push your
branch and watch the PR/status check appear on GitHub.

## Jenkins (host maintainer only)

This project uses **one shared Jenkins instance**, run by a single
designated team member — not something every teammate spins up
individually. If that's you:

```bash
# First time / after changing jenkins/Dockerfile
docker compose -p foodgorilla up -d --build jenkins

# Daily pause/resume (no rebuild needed)
docker compose -p foodgorilla stop jenkins
docker compose -p foodgorilla start jenkins

# Codespaces only: re-expose the forwarded port after a start
gh codespace ports visibility 8080:public -c $CODESPACE_NAME
```

Credentials required in Jenkins (**Manage Jenkins → Credentials → System
→ Global**, not the personal `admin` store):
- `github-token` — GitHub username + PAT (repo + repo:status scopes)
- `nutritrack-db-password` — the same value as `POSTGRES_PASSWORD` in `.env`

If you ever need to fully reset the Jenkins instance (new host, corrupted
state, etc.), this is a one-time setup, not a routine task — recreate the
Multibranch Pipeline job and the two credentials above from scratch.

## Repo structure

```
Food-Gorilla/
├── database/       # Dockerfile + init.sql
├── backend/        # Flask API
├── frontend/       # Express frontend
├── jenkins/        # Custom Jenkins image (adds Ansible)
├── ansible/        # playbook.yml - preflight + post-deploy smoke test
├── docker-compose.yml
├── docker-compose.override.yml   # host ports, auto-merged locally
├── docker-compose.dev.yml        # optional hot-reload bind mounts, opt-in only
├── Jenkinsfile
└── .env.example
```