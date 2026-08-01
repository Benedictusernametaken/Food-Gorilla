pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        // If Jenkins itself crashes mid-build, the default durability
        // setting tries to RESUME that build on next startup by
        // reconnecting to its old process handles. Since the whole
        // container (and everything in it) is gone by then, that resume
        // attempt is reconnecting to something that no longer exists —
        // which is the likely cause of Jenkins crashing again shortly
        // after every restart. This setting tells Jenkins to just mark
        // an interrupted build as failed on restart instead of trying
        // (and failing) to resume it.
        durabilityHint('PERFORMANCE_OPTIMIZED')
    }

    // NOTE: no pollSCM trigger here anymore. Under Multibranch Pipeline,
    // polling/branch-discovery is configured at the JOB level instead
    // ("Scan Repository Triggers -> Periodically", e.g. every 5 minutes),
    // since Multibranch also needs to detect new/deleted branches, which
    // a Jenkinsfile-level pollSCM trigger can't do on its own. Keeping
    // both would just mean two redundant polling mechanisms.

    environment {
        APP_NAME          = 'foodgorilla'
        POSTGRES_USER     = 'foodgorilla_admin'
        POSTGRES_PASSWORD = credentials('nutritrack-db-password') 
        POSTGRES_DB       = 'foodgorilla_db'
        
        FLASK_APP         = 'app.main'
        FLASK_ENV         = 'production'
        PYTHONPATH        = '/app'

        // Explicitly naming ONLY the base file disables Compose's automatic
        // merge of docker-compose.override.yml, so the test stack never
        // inherits host port bindings (see docker-compose.override.yml).
        COMPOSE_TEST_FILES = '-f docker-compose.yml'

        // Forces Compose to build images ONE AT A TIME instead of all
        // concurrently via BuildKit. This Codespace has no swap configured
        // (and can't have swap added — containers can't call swapon), so
        // building database+backend+frontend simultaneously, on top of the
        // Jenkins JVM and Docker daemon, previously spiked memory enough
        // to kill every running container at once. Sequential builds take
        // a bit longer but keep peak memory well below that ceiling.
        COMPOSE_PARALLEL_LIMIT = '1'
    }

    stages {
        // STAGE 1: CLEAN WORKSPACE & FETCH CODE
        stage('Checkout Code') {
            steps {
                echo 'Purging host workspace folder caches entirely...'
                deleteDir() 
                checkout scm
            }
        }

        // STAGE 1.5: HOST PREFLIGHT CHECKS (runs for every branch, before any build)
        // Moved to run right after Checkout — this is the cheapest, fastest
        // check ("is this host even capable of running Docker") and should
        // fail fast before any heavier stage spends time building images.
        stage('Preflight Checks via Ansible') {
            steps {
                echo '🔍 Verifying host prerequisites (Docker, Compose, disk space)...'
                // Read-only checks only — never touches docker compose up/down,
                // never interacts with the running app stack.
                sh 'ansible-playbook -i "localhost," ansible/playbook.yml --tags preflight'
            }
        }

        // STAGE 1.6: CODE QUALITY CHECKS — Ming Hao
        stage('Code Quality') {
            steps {
                echo '🔎 Running code quality checks (Ruff + mypy)...'
                sh '''
                    docker compose -f docker-compose.yml build backend
                    docker compose -f docker-compose.yml run --rm backend ruff check .
                    docker compose -f docker-compose.yml run --rm backend mypy .
                '''
            }
            post {
                always {
                    // "run --rm backend ..." only removes the transient backend
                    // container it creates — but backend depends_on database
                    // (condition: service_healthy), so Compose also starts a
                    // real, PERSISTENT database container as a side effect.
                    // Nothing was ever stopping/removing that afterward, so
                    // every single run across every branch/PR left an orphaned
                    // database container + volume behind indefinitely. This is
                    // a confirmed contributor to the disk-space investigation
                    // earlier — visible as long-lived "Exited" database
                    // containers per branch in `docker system df -v`.
                    sh 'docker compose -f docker-compose.yml down -v --remove-orphans || true'
                }
            }
        }

        stage('Debug Frontend Build') {
            steps {
                sh '''
                    docker compose -f docker-compose.yml build --no-cache frontend
                    docker compose -f docker-compose.yml run --rm frontend cat /app/package.json
                '''
            }
            post {
                always {
                    // Same orphaned-dependency-container issue as Code Quality above.
                    sh 'docker compose -f docker-compose.yml down -v --remove-orphans || true'
                }
            }
        }

        stage('Frontend Code Quality') {
            steps {
                sh '''
                    docker compose -f docker-compose.yml run --rm frontend npm run lint
                '''
            }
            post {
                always {
                    // Same orphaned-dependency-container issue as Code Quality above.
                    sh 'docker compose -f docker-compose.yml down -v --remove-orphans || true'
                }
            }
        }

        stage('Dockerfile Quality') {
            steps {
                sh '''
                    echo "Checking backend Dockerfile..."
                    docker run --rm -i hadolint/hadolint \
                        hadolint --ignore DL3008 --failure-threshold error - < backend/Dockerfile

                    echo "Checking frontend Dockerfile..."
                    docker run --rm -i hadolint/hadolint \
                        hadolint --ignore DL3008 --failure-threshold error - < frontend/Dockerfile

                    echo "Checking database Dockerfile..."
                    docker run --rm -i hadolint/hadolint \
                        hadolint --ignore DL3008 --failure-threshold error - < database/Dockerfile

                    echo "Checking jenkins Dockerfile..."
                    docker run --rm -i hadolint/hadolint \
                        hadolint --ignore DL3008 --failure-threshold error - < jenkins/Dockerfile
                '''
            }
        }

        // STAGE 2: ISOLATED TESTING (Runs first!)
        stage('Integration Testing') {
            steps {
                echo '🧹 DEFENSIVE CLEANUP: Wiping any stale test containers...'
                // Using "-p ${APP_NAME}_test_${BUILD_NUMBER}" guarantees this
                // command ONLY touches test setups AND that concurrent builds
                // (e.g. two branches/PRs testing around the same time) never
                // collide on identical container names. Without the build
                // number, every branch/PR shared the literal same project name
                // "foodgorilla_test" — if one build's cleanup fired while
                // another's test stage was still mid-run, the second build
                // would hit "Error response from daemon: No such container",
                // since its containers had just been deleted out from under it
                // by the first build's teardown. BUILD_NUMBER is unique per
                // run within this job, so each build now gets a fully isolated
                // project namespace.
                sh 'docker compose ${COMPOSE_TEST_FILES} -p ${APP_NAME}_test_${BUILD_NUMBER} down -v --remove-orphans || true'

                echo 'Building and starting the full dependency chain (database -> backend -> frontend)...'
                // Now that backend has its own HEALTHCHECK and frontend has
                // depends_on: backend: condition: service_healthy, Compose
                // itself brings services up in the correct order and BLOCKS
                // (then fails the whole command) if a dependency never
                // becomes healthy. This replaces the old manual staggering
                // of "up -d database frontend" -> "sleep 10" -> "up -d backend".
                //
                // Explicitly naming only the app services (never "jenkins")
                // here too — even under the separate "_test" project
                // namespace, an unqualified "up" would still spin up an
                // unnecessary throwaway jenkins container every single run.
                sh 'docker compose ${COMPOSE_TEST_FILES} -p ${APP_NAME}_test_${BUILD_NUMBER} up -d --build database frontend backend'

                echo 'Checking container status...'
                sh 'docker compose ${COMPOSE_TEST_FILES} -p ${APP_NAME}_test_${BUILD_NUMBER} ps'

                echo 'Verifying backend health endpoint content (not just container status)...'
                // By this point Docker's own HEALTHCHECK already confirmed the
                // backend responds with HTTP 200 before frontend was allowed to
                // start — no retry loop needed here anymore. This check instead
                // confirms the JSON body itself reports a real DB connection,
                // which the container-level HEALTHCHECK doesn't inspect.
                sh '''
                    docker compose ${COMPOSE_TEST_FILES} -p ${APP_NAME}_test_${BUILD_NUMBER} exec -T backend python -c "
import urllib.request, json, sys
res = urllib.request.urlopen('http://127.0.0.1:5000/health-check', timeout=5)
body = json.loads(res.read())
print('Backend response:', body)
if body.get('database_connectivity') != 'CONNECTED':
    print('!!! Backend responded but database is not actually connected !!!')
    sys.exit(1)
"
                '''
            }
            post {
                always {
                    echo '--- CAPTURING LOGS (post-attempt, for diagnostics) ---'
                    sh 'docker compose ${COMPOSE_TEST_FILES} -p ${APP_NAME}_test_${BUILD_NUMBER} logs backend > backend_debug.log 2>&1 || true'
                    sh 'docker compose ${COMPOSE_TEST_FILES} -p ${APP_NAME}_test_${BUILD_NUMBER} logs frontend > frontend_debug.log 2>&1 || true'
                    sh 'cat backend_debug.log || true'
                    sh 'cat frontend_debug.log || true'
                    archiveArtifacts artifacts: 'backend_debug.log,frontend_debug.log', allowEmptyArchive: true

                    echo 'Cleaning up isolated test architecture environment...'
                    sh 'docker compose ${COMPOSE_TEST_FILES} -p ${APP_NAME}_test_${BUILD_NUMBER} down -v --remove-orphans || true'
                }
            }
        }

        // STAGE 2.5: AUTO-OPEN PR TO MAIN (feature branches only, after tests pass)
        stage('Open Pull Request to main') {
            when {
                // Only feature/* branches reach here — main's own runs skip
                // this (main has nothing to open a PR against itself for),
                // and if Integration Testing failed, Jenkins never reaches
                // this stage at all, so a failed test run never opens a PR.
                branch pattern: 'feature/.*', comparator: 'REGEXP'
            }
            steps {
                echo '📬 Opening pull request into main...'
                withCredentials([usernamePassword(credentialsId: 'github-token', usernameVariable: 'GH_USER', passwordVariable: 'GH_TOKEN')]) {
                    sh '''
                        HTTP_CODE=$(curl -s -o response.json -w "%{http_code}" -X POST \
                            -H "Authorization: token $GH_TOKEN" \
                            -H "Accept: application/vnd.github+json" \
                            https://api.github.com/repos/Benedictusernametaken/Food-Gorilla/pulls \
                            -d "{\\"title\\":\\"Merge ${BRANCH_NAME} into main\\",\\"head\\":\\"${BRANCH_NAME}\\",\\"base\\":\\"main\\",\\"body\\":\\"Automated PR opened after Jenkins pipeline succeeded on ${BRANCH_NAME}.\\"}")

                        echo "GitHub API responded with HTTP $HTTP_CODE"
                        cat response.json

                        # 201 = PR created. 422 = a PR already exists for this
                        # branch (harmless — don't fail the build over it).
                        # Anything else is a genuine problem worth failing loudly for.
                        if [ "$HTTP_CODE" != "201" ] && [ "$HTTP_CODE" != "422" ]; then
                            echo "!!! Unexpected response while creating pull request !!!"
                            exit 1
                        fi
                    '''
                }
            }
        }

        // STAGE 3: PRODUCTION DEPLOYMENT (Only runs if Testing succeeds, AND only on main!)
        stage('Deploy to Production') {
            when {
                // Under Multibranch, every branch gets its own job. Without
                // this guard, a teammate's feature branch push would also
                // deploy straight to production — only merges to main should.
                branch 'main'
            }
            steps {
                echo 'Cleaning up and starting production services...'
                // No -f flags here, so Compose auto-merges docker-compose.yml +
                // docker-compose.override.yml and gets real host ports as intended.
                //
                // CRITICAL: explicitly name only the app services here.
                // A bare "docker compose up" with no service list would ALSO
                // bring up the "jenkins" service defined in this same compose
                // file — meaning a running Jenkins pipeline would try to
                // recreate/restart the very Jenkins container it's executing
                // inside of. Never remove this explicit service list.
                // Now that docker-compose.yml no longer hardcodes a global
                // "name:", Compose would otherwise derive a project name
                // from whatever folder this happens to run in — which for
                // Jenkins is its own internal workspace path, unrelated to
                // the actual app. Pinning "-p foodgorilla" here keeps
                // production deploys stable and predictable regardless of
                // that path, without reintroducing a name that silently
                // applies to every directory copy everywhere (the bug that
                // caused Jenkins to keep getting killed mid-pipeline).
                // CRITICAL FIX: "docker compose down" has NO way to scope to
                // specific services — it always tears down the ENTIRE named
                // project, jenkins included, no matter what's listed after
                // it. This was silently killing the real Jenkins container
                // every single time this stage ran. "stop" and "rm" DO
                // support per-service scoping, so we use those instead —
                // this achieves the same clean teardown without ever
                // touching anything outside database/frontend/backend.
                sh '''
                    docker compose -p foodgorilla stop database frontend backend || true
                    docker compose -p foodgorilla rm -f database frontend backend || true
                    docker compose -p foodgorilla pull database frontend backend || true
                    docker compose -p foodgorilla up -d --build database frontend backend
                '''
            }
        }
    


        // STAGE 4: RUN ANSIBLE PLAYBOOK (only on main, same reasoning as Stage 3)
        stage('Deploy Application via Ansible') {
            when {
                branch 'main'
            }
            steps {
                echo '🚀 Running post-deployment verification via Ansible...'
                // This does NOT deploy anything — Stage 3 already did that.
                // Same playbook file as the preflight stage, different tag.
                sh 'ansible-playbook -i "localhost," ansible/playbook.yml --tags smoke_test'
            }
        }
    }
    

    // 🌟 UNIFIED GLOBAL POST BLOCK (Merged GitHub notifications and console echoes)
    post {
        success {
            githubNotify(
                credentialsId: 'github-token',
                context: 'Jenkins CI/CD Pipeline',
                description: 'Build passed successfully!',
                status: 'SUCCESS',
                account: 'Benedictusernametaken',
                repo: 'Food-Gorilla',
                sha: env.GIT_COMMIT ?: sh(script: 'git rev-parse HEAD', returnStdout: true).trim()
            )
            echo "🎉 Build #${BUILD_NUMBER} Passed! The 3-tier architecture is verified and secure."
        }
        failure {
            githubNotify(
                credentialsId: 'github-token',
                context: 'Jenkins CI/CD Pipeline',
                description: 'Pipeline Failed!',
                status: 'FAILURE',
                account: 'Benedictusernametaken',
                repo: 'Food-Gorilla',
                sha: env.GIT_COMMIT ?: sh(script: 'git rev-parse HEAD', returnStdout: true).trim()
            )
            echo "❌ Build #${BUILD_NUMBER} Failed! Check the logs or integration test diagnostics above."
        }
    }
}