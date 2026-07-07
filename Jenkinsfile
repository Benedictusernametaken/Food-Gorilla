pipeline {
    agent any

    options {
        disableConcurrentBuilds()
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

        // STAGE 2: ISOLATED TESTING (Runs first!)
        stage('Integration Testing') {
            steps {
                echo '🧹 DEFENSIVE CLEANUP: Wiping any stale test containers...'
                // Using "-p ${APP_NAME}_test" guarantees this command ONLY touches test setups
                sh 'docker compose ${COMPOSE_TEST_FILES} -p ${APP_NAME}_test down -v --remove-orphans || true'

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
                sh 'docker compose ${COMPOSE_TEST_FILES} -p ${APP_NAME}_test up -d --build database frontend backend'

                echo 'Checking container status...'
                sh 'docker compose ${COMPOSE_TEST_FILES} -p ${APP_NAME}_test ps'

                echo 'Verifying backend health endpoint content (not just container status)...'
                // By this point Docker's own HEALTHCHECK already confirmed the
                // backend responds with HTTP 200 before frontend was allowed to
                // start — no retry loop needed here anymore. This check instead
                // confirms the JSON body itself reports a real DB connection,
                // which the container-level HEALTHCHECK doesn't inspect.
                sh '''
                    docker compose ${COMPOSE_TEST_FILES} -p ${APP_NAME}_test exec -T backend python -c "
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
                    sh 'docker compose ${COMPOSE_TEST_FILES} -p ${APP_NAME}_test logs backend > backend_debug.log 2>&1 || true'
                    sh 'docker compose ${COMPOSE_TEST_FILES} -p ${APP_NAME}_test logs frontend > frontend_debug.log 2>&1 || true'
                    sh 'cat backend_debug.log || true'
                    sh 'cat frontend_debug.log || true'
                    archiveArtifacts artifacts: 'backend_debug.log,frontend_debug.log', allowEmptyArchive: true

                    echo 'Cleaning up isolated test architecture environment...'
                    sh 'docker compose ${COMPOSE_TEST_FILES} -p ${APP_NAME}_test down -v --remove-orphans || true'
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
                sh '''
                    docker compose down --remove-orphans || true
                    docker compose pull database frontend backend || true
                    docker compose up -d --build database frontend backend
                '''
            }
        }
    


        // STAGE 4: RUN ANSIBLE PLAYBOOK (only on main, same reasoning as Stage 3)
        stage('Deploy Application via Ansible') {
            when {
                branch 'main'
            }
            steps {
                echo '🚀 Initiating Automated Ansible Deployment...'
                
                // Runs the optimized playbook using the repository configuration
                sh "ansible-playbook your-playbook-name.yml --extra-vars 'app_workspace=${WORKSPACE} project_namespace=${APP_NAME}_${BUILD_NUMBER}'"
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