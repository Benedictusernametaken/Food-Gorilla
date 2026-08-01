# Food Gorilla — SonarQube Code Quality

What the `Code Quality - SonarQube` stage does, how to set up the server
it needs, and how to read the results.

Owner: Ryan. Linter stages (Ruff / mypy / eslint / hadolint): Ming Hao.

---

## 1. What this adds, and what it doesn't

We already have linters. This is **not** a replacement for them, and it is
honest to say there is overlap — SonarQube's Python and JavaScript rules
cover some of the same ground as Ruff and ESLint.

What linters structurally cannot do, and SonarQube can:

| Capability | Why a linter can't |
|---|---|
| **Cross-file data flow** | A linter checks one file at a time. SonarQube can follow a value from a request parameter through several functions and files. |
| **Duplication detection** | A linter can't see that two files share 40 near-identical lines. |
| **History and trend** | Technical debt tracked build over build, so you can see whether the codebase is improving. |
| **New code vs overall code** | Hold new work to a higher standard without having to fix everything that already exists first. |
| **One gate over everything** | A single pass/fail across bugs, smells, duplication and coverage, instead of four stages each failing separately. |

Short version: *linters catch style and obvious mistakes per file;
SonarQube measures the codebase as a whole and tracks whether it's getting
better or worse.*

---

## 2. Versions are pinned

| Component | Version |
|---|---|
| SonarQube server | `sonarqube:2025.1-community` |
| Scanner CLI | `sonarsource/sonar-scanner-cli:11` |

Analysis results change between versions. If the server and scanner drift,
findings change without the code changing, and nobody can tell which is
which. Bump both here and in the `Jenkinsfile` in the same PR.

> If you ran the earlier `sonarqube:10-community` image locally and saw the
> red "no longer active" banner, that is why this pins a current release.

---

## 3. Server setup (Jenkins host only, once)

The pipeline needs a SonarQube server running on the same Docker host as
Jenkins. It is **not** in `docker-compose.yml` — that file is deliberately
left alone, and a bare `docker compose up`/`down` in this repo is dangerous
because `jenkins` is a service in it.

Run these once on the Jenkins host:

```bash
# Elasticsearch (inside SonarQube) needs this or the container won't boot
sudo sysctl -w vm.max_map_count=524288

docker network create sonar-net

docker run -d --name sonarqube \
  --restart unless-stopped \
  --network sonar-net \
  -p 9000:9000 \
  -v sonarqube_data:/opt/sonarqube/data \
  -v sonarqube_extensions:/opt/sonarqube/extensions \
  -v sonarqube_logs:/opt/sonarqube/logs \
  sonarqube:2025.1-community
```

Give it 2–3 minutes, then confirm:

```bash
docker logs sonarqube | tail -20     # want: "SonarQube is operational"
```

The named volumes matter — without them every container restart wipes the
project history, which is the main thing SonarQube offers over a linter.

### Then, in the SonarQube web UI (port 9000)

1. Log in as `admin` / `admin`, set a real password.
2. **Create a local project**, key exactly `foodgorilla` (must match
   `sonar-project.properties`).
3. **My Account → Security → Generate token**, type *Global Analysis
   Token*. Copy it — it is shown once.

### Then, in Jenkins

**Manage Jenkins → Credentials → System → Global → Add credentials**

- Kind: **Secret text**
- ID: `sonar-token` (exactly — the Jenkinsfile looks this up by ID)
- Secret: the token you just generated

Without this credential the stage fails immediately at `withCredentials`.

---

## 4. What the stage does

1. Checks the `sonar-net` network and `sonarqube` container exist, and
   fails with a pointer here if not.
2. Pipes `backend/`, `frontend/` and `sonar-project.properties` into the
   `sonar-src` named volume.
3. Runs the pinned scanner container on `sonar-net`, uploading results.

**Why the tar pipe instead of just mounting the workspace.** Jenkins runs
inside a container but drives the *host's* Docker daemon through the
mounted socket. A `-v $(pwd):/usr/src` bind mount asks the host to mount a
path that only exists inside the Jenkins container — you get an empty
directory, silently, with no error. Every containerised scanner stage in
this pipeline works around it the same way.

---

## 5. Reading the results

Dashboard: `http://<jenkins-host>:9000` → project `foodgorilla`.

Baseline from the first analysis (2026-07-26):

| Metric | Value | What it means |
|---|---|---|
| Security | 4 issues, **E** | Worst-rated area — look here first |
| Reliability | 6 issues, **C** | Likely real bugs |
| Maintainability | 96 issues, **A** | High count but low severity; normal |
| Security Hotspots | 35, **E** | Not bugs — code a human should review |
| Coverage | **0.0%** | See section 7 |
| Duplications | 11.3% of 8.9k lines | A bit high; worth a look |

**"Quality Gate: Passed" on a first analysis is not meaningful.** The
default gate judges *new* code only, and on a first run there is none. Read
the numbers above, not the badge.

Grades are relative, not absolute: **A** on Maintainability with 96 open
issues means the estimated remediation time is small next to the size of
the codebase — not that there is nothing to fix.

---

## 6. Phase 1 (now) → Phase 2 (enforcement)

**Phase 1, current.** `SONAR_GATE_WAIT = 'false'`. The scanner uploads and
exits; the dashboard updates and the build never fails. Deliberate: the
default gate judges new code, so switching it on without warning would
block whoever pushes next over their own in-progress work.

**Phase 2.** Change that one value to `'true'`. The scanner then waits for
the gate and fails the build when it fails. Do it in a small dedicated PR,
after the team has agreed the gate's thresholds.

Same pattern as the security scanning stages: report first, enforce once
everyone has seen what the tool actually says.

---

## 7. Known gap: coverage is 0%

`backend/tests/` has 12 pytest files, and **the pipeline never runs them.**
Integration Testing only checks that containers start and the database
connects. So 0% is accurate, not a misconfiguration.

Fixing it is a separate PR, roughly:

1. Add `pytest-cov` to `backend/requirements.txt`
2. Run the tests with coverage in the pipeline and write `coverage.xml`
3. Add `sonar.python.coverage.reportPaths=coverage.xml` to
   `sonar-project.properties`

Left out of this change on purpose — it touches `backend/requirements.txt`,
which teammates may be editing, and it is a bigger change than adding a
scanner. Worth doing: it would make the pipeline actually verify the tests
that already exist.

---

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `docker network 'sonar-net' does not exist` | Server setup never done — section 3 |
| `the 'sonarqube' container is not running` | `docker start sonarqube` on the Jenkins host |
| Stage fails at `withCredentials` | The `sonar-token` credential is missing or has a different ID — section 3 |
| SonarQube won't boot, logs mention `max virtual memory areas` | `sudo sysctl -w vm.max_map_count=524288`, then `docker restart sonarqube` |
| `You're running a version of SonarQube that is no longer active` | You're on an old image. Section 2 pins a current one |
| Analysis succeeds but the project looks empty | `sonar.projectKey` in `sonar-project.properties` doesn't match the project created in the UI |
| Jenkins host runs out of memory | SonarQube wants ~2GB and this box has no swap. Don't run a first analysis while a build is in flight |

---

## Quick reference

```bash
# On the Jenkins host
docker start sonarqube
docker logs sonarqube | tail -20

# Scan by hand from a repo clone (bind mount is fine outside Jenkins)
docker run --rm --network sonar-net -v "$(pwd):/usr/src" \
  sonarsource/sonar-scanner-cli:11 \
  -Dsonar.host.url=http://sonarqube:9000 \
  -Dsonar.token=<your-token>
```

Questions: SonarQube → Ryan. Linters → Ming Hao.
