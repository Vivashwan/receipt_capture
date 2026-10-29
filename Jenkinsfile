// End-to-end pipeline: boots the full stack, seeds it, runs the Selenium suites in Python,
// JavaScript and C#, publishes JUnit results, and adds an AI triage of any failures.
//
// Agent needs: Docker (with compose), Python 3.10+, Node 20, Google Chrome. Each suite runs through
// e2e/run-suite.sh (shared with GitLab CI and GitHub Actions); without .NET on the agent the C#
// suite runs in the .NET SDK container.
// Credentials (Secret text): receipt-capture-db-root-password, receipt-capture-admin-password.

pipeline {
	agent { label 'e2e' }

	options {
		timeout(time: 90, unit: 'MINUTES')
		disableConcurrentBuilds()  // one stack per agent: the suites share its ports and site
		buildDiscarder(logRotator(numToKeepStr: '20'))
	}

	parameters {
		booleanParam(name: 'SMOKE_ONLY', defaultValue: false, description: 'Run only the smoke tests of each suite')
		string(name: 'COMPOSE_PROJECT', defaultValue: 'receipt-capture-ci', description: 'Docker Compose project to start (or reuse)')
		booleanParam(name: 'KEEP_STACK', defaultValue: false, description: 'Leave the stack running after the build')
	}

	environment {
		COMPOSE_PROJECT_NAME = "${params.COMPOSE_PROJECT}"
		DB_ROOT_PASSWORD = credentials('receipt-capture-db-root-password')
		ADMIN_PASSWORD = credentials('receipt-capture-admin-password')
		SITE_NAME = 'erp.localhost'
		// The browser must use the site name: socket.io rejects other origins (see README)
		BASE_URL = 'http://erp.localhost:8080'
		HEADLESS = '1'
	}

	stages {
		stage('Start stack') {
			steps {
				sh '''
					docker compose up -d --build
					docker compose wait create-site ollama-pull
				'''
			}
		}

		stage('Seed test data') {
			steps {
				sh 'docker compose exec -T backend bench --site "$SITE_NAME" execute receipt_capture.e2e_setup.setup_site'
			}
		}

		stage('Triage self-test') {
			steps {
				sh 'python3 -m unittest discover -s e2e/triage'
			}
		}

		// Sequential on purpose: the suites share one site, and each one's later tests use data its
		// earlier tests create. catchError lets every suite run and report even if one fails.
		stage('Python suite (pytest)') {
			steps { runSuite('python') }
		}
		stage('JavaScript suite (Mocha)') {
			steps { runSuite('js') }
		}
		stage('C# suite (NUnit)') {
			steps { runSuite('dotnet') }
		}
	}

	post {
		always {
			junit testResults: 'e2e/**/artifacts/junit.xml, e2e/**/TestResults/junit.xml', allowEmptyResults: true
			sh '''
				docker compose logs --no-color --tail 300 backend queue-long websocket frontend > compose.log 2>&1 || true
				python3 e2e/triage/triage.py \
					--results 'e2e/**/junit.xml' --artifacts e2e --logs compose.log --out triage \
					|| echo "Triage failed; the test results above are unaffected"
			'''
			archiveArtifacts artifacts: 'triage.md, triage.json, compose.log, e2e/**/artifacts/**, e2e/**/TestResults/**', allowEmptyArchive: true
			script {
				if (!params.KEEP_STACK) {
					// Keep the downloaded model between builds; drop the site, database and queue
					sh '''
						docker compose down
						docker volume rm "${COMPOSE_PROJECT_NAME}_sites" "${COMPOSE_PROJECT_NAME}_db-data" "${COMPOSE_PROJECT_NAME}_redis-queue-data" || true
					'''
				}
			}
		}
	}
}

def runSuite(String suite) {
	catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
		sh "e2e/run-suite.sh ${suite} ${params.SMOKE_ONLY ? '--smoke' : ''}"
	}
}
