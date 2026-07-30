# Food Gorilla — Security Scanning Guide

How the pipeline checks for known vulnerabilities, how to run the same
checks yourself, and what to do when something goes red.

Owners: Trivy stage — Alden. Dependency-Check stage — Ryan.

---

## 1. What we scan, and why two scanners

Our tests answer "does it work?" They cannot answer:

> Are we shipping known, publicly documented vulnerabilities that we
> inherited from base images and third-party libraries?

Nobody is going to hand-check every dependency against a CVE database on
every release, so the pipeline does it. Two stages, two different
questions:

| Stage | Tool | What it scans | What it catches |
|---|---|---|---|
| `Security Scanning` | **Trivy** | The built Docker **images** | Vulnerable OS packages in the base image (`python:3.10-slim`, `node:18-slim`) plus libraries installed inside the container |
| `Security Scan - Dependencies` | **OWASP Dependency-Check** | The **source manifests** (`backend/requirements.txt`, `frontend/package-lock.json`) | Third-party libraries with published CVEs, straight from the NVD database |

**These are not the same job done twice.** A vulnerable OS package baked
into `python:3.10-slim` is invisible to Dependency-Check, which only reads
manifests. An outdated Flask pinned in `requirements.txt` is a
source-level problem Trivy's image scan is not designed to answer.
Running both is what "defense in depth" actually means here.

Both stages run on **every branch and every trigger**, including the
nightly timer. Nightly matters because a CVE can be published tomorrow
against code that was already clean today.

---

## 2. Versions are pinned on purpose

| Tool | Version |
|---|---|
| Trivy | `aquasec/trivy:0.72.0` |
| OWASP Dependency-Check | `owasp/dependency-check:12.1.0` |

Scanner output changes between versions. If one person runs `:latest` and
another runs a pinned version, you get two different findings lists for
identical code and an argument in the PR about who is right. Pinning ends
that.

If we bump a version, we bump it here and in the `Jenkinsfile` in the same
PR — never silently.

---

## 3. Nothing to install

Both scanners run as **Docker containers**, invoked by the pipeline. There
is no "install Trivy on the Jenkins server" step, no JDK to manage, and
nothing that breaks when the Jenkins container is rebuilt.

To run either scanner yourself you need Docker, which you already have.
See section 6.

---

## 4. NVD API key (Dependency-Check only)

Dependency-Check downloads the NVD CVE database. Without an API key that
first sync is very slow and rate-limited; with one it is much faster.

1. Request a free key: <https://nvd.nist.gov/developers/request-an-api-key>
   (arrives by email, usually within minutes)
2. In Jenkins: **Manage Jenkins → System → Global properties →
   Environment variables → Add**
   - Name: `NVD_API_KEY`
   - Value: the key

That is the **only** Jenkins configuration either stage needs.

The pipeline is written so a missing key **degrades to slow, not broken** —
it prints a warning and carries on. The key is kept out of build logs
(`set +x` around that command). Treat it as a low-sensitivity secret:
don't commit it, don't paste it into screenshots.

---

## 5. Where the databases live

Both scanners cache their vulnerability data in **named Docker volumes**,
not in the workspace:

| Volume | Used by |
|---|---|
| `trivy-cache` | Trivy's vulnerability DB, and the staged `.trivyignore` |
| `dc-data` | The NVD CVE database |
| `dc-work` | Scratch space for staging manifests and extracting the report |

This matters because `Checkout Code` runs `deleteDir()` on every single
build. Anything cached in the workspace would be re-downloaded from
scratch every time — for the NVD database that is the difference between
seconds and hours.

**Why volumes and not bind mounts.** Jenkins runs inside a container but
talks to the *host's* Docker daemon through the mounted socket. A
`-v $(pwd):/src` bind mount asks the host to mount a path that only exists
inside the Jenkins container, so you get an empty directory instead of the
workspace — silently, with no error. Both stages work around this the same
way: pipe files in and out of a named volume with `tar`. That is why the
Dependency-Check stage stages its manifests before scanning and extracts
the report afterwards instead of just mounting the workspace.

---

## 6. Running the scanners yourself

Build the images first. This starts nothing, so there is nothing to tear
down afterwards:

```bash
cp -n .env.example .env
docker compose -f docker-compose.yml -p foodgorilla_test build backend frontend
docker images | grep foodgorilla_test
```

> ⚠️ Never run a bare `docker compose down` or `up` in this repo. `down`
> cannot be scoped to individual services and tears down the whole named
> project — and `jenkins` is a service in the same compose file, so a bare
> `down` kills the Jenkins container mid-build. Always pass `-p` and name
> services explicitly. The `build` command above sidesteps this entirely
> by never starting anything.

**Trivy, report-only:**

```bash
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:0.72.0 image --scanners vuln --severity HIGH,CRITICAL \
  foodgorilla_test-backend:latest
```

Report-only just means omitting `--exit-code 1`. Swap in
`foodgorilla_test-frontend:latest` for the frontend.

**Dependency-Check, report-only:**

```bash
mkdir -p ~/fg-dc-report ~/fg-dc-data
docker run --rm \
  -v "$(pwd)":/src:ro \
  -v ~/fg-dc-data:/usr/share/dependency-check/data \
  -v ~/fg-dc-report:/report \
  owasp/dependency-check:12.1.0 \
  --project foodgorilla \
  --scan /src/backend --scan /src/frontend \
  --exclude "**/node_modules/**" \
  --enableExperimental \
  --format HTML --out /report \
  --failOnCVSS 11 \
  --nvdApiKey "$NVD_API_KEY"
```

Then open `~/fg-dc-report/dependency-check-report.html`.

Bind mounts *do* work here, because on your own machine the Docker daemon
and your files are on the same host. Only Jenkins has the constraint
described in section 5.

**`--enableExperimental` is not optional.** Without it Dependency-Check
silently skips Python entirely and `backend/requirements.txt` goes
unscanned. It reports no error when this happens, which is exactly what
makes it easy to get wrong.

---

## 7. Phase 1 (now) → Phase 2 (enforcement)

**Phase 1, where we are:** both scanners produce full reports but do not
fail the build. On day one the images and manifests contain findings
nobody has triaged. Hard-failing every push over pre-existing debt would
block the whole team and teach everyone to ignore the stage.

**Phase 2:** once we have triaged the baseline together, flip to
enforcement in a small dedicated PR:

| Stage | Change |
|---|---|
| Dependency-Check | `DC_FAIL_CVSS` `'11'` → `'7'` (fail on CVSS ≥ 7.0) |
| Trivy | add `--exit-code 1` |

`DC_FAIL_CVSS = '11'` is deliberate: CVSS scores cap at 10, so a threshold
of 11 can never trigger. One line to flip, nothing else to rewrite.

**Accepting a finding instead of fixing it** is sometimes the right call —
no fix published upstream, or the vulnerable code path isn't reachable
from our app:

- Trivy: add the CVE ID to `.trivyignore` at the repo root, with a comment
  saying who reviewed it and when. Alden's existing entries are the model.
- Dependency-Check: write a suppression XML file and pass
  `--suppression <file>`.

Either way the rule is the same: **a comment saying why, and who decided**.
An unexplained ignore entry is indistinguishable from someone silencing a
real problem.

---

## 8. Reading the results

On the Jenkins build page, under **Archived artifacts**:

- `trivy-backend-report.txt`, `trivy-frontend-report.txt` — image findings
- `dependency-check-report/dependency-check-report.html` — dependency
  findings, readable in a browser
- `dependency-check-report/dependency-check-report.json` — same data,
  machine-readable

Trivy's tables also print into the console log, so you can skim image
findings without downloading anything.

Reading a Trivy row: the columns that matter are **severity**, whether a
**fixed version** exists, and which package is affected. A HIGH with no
fix available is a different decision from a HIGH that a version bump
resolves.

---

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Dependency-Check takes forever on its first run | Expected — that is the NVD database downloading into the `dc-data` volume. Later builds are incremental. Set `NVD_API_KEY` (section 4) to speed it up a lot |
| NVD `403` / `404` errors | Missing or typo'd API key. Also just retry: NVD has flaky days |
| Dependency-Check reports nothing for the backend | `--enableExperimental` missing — Python analysers are off by default and fail silently |
| `no such file or directory` while staging manifests | One of `backend/requirements.txt`, `frontend/package.json`, `frontend/package-lock.json` was renamed or moved. Update the `tar` line in the stage |
| A scan runs clean and it looks too good | Check the database actually updated — a rate-limited scanner will happily scan against a stale or empty database |
| Trivy fails on the image name | The tag the stage scans must match what the build produced. Run `docker images` on the Jenkins host to see the real names |
| Everything slow / Jenkins container killed | This box has no swap. Don't run heavy local builds or a first-time NVD sync while a pipeline build is in flight |
| Container-name conflicts in Integration Testing | Two branches' test stages collide over the shared `foodgorilla_test` compose project. Don't push while a teammate is mid-build; re-run when theirs finishes |

---

## Quick reference

```bash
# Build the images the scanners target (starts nothing)
docker compose -f docker-compose.yml -p foodgorilla_test build backend frontend

# Image scan
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:0.72.0 image --scanners vuln --severity HIGH,CRITICAL \
  foodgorilla_test-backend:latest

# Dependency scan (from repo root)
docker run --rm -v "$(pwd)":/src:ro -v ~/fg-dc-data:/usr/share/dependency-check/data \
  -v ~/fg-dc-report:/report owasp/dependency-check:12.1.0 \
  --project foodgorilla --scan /src/backend --scan /src/frontend \
  --exclude "**/node_modules/**" --enableExperimental \
  --format HTML --out /report --failOnCVSS 11 --nvdApiKey "$NVD_API_KEY"
```

Questions: Trivy → Alden. Dependency-Check → Ryan.
