#!/usr/bin/env bash
# Runs one Selenium suite against a running stack, writing JUnit XML where CI looks for it:
#   e2e/python/artifacts/junit.xml, e2e/js/artifacts/junit.xml, e2e/dotnet/ReceiptCapture.E2E/TestResults/junit.xml
#
#   e2e/run-suite.sh python|js|dotnet [--smoke]
#
# Shared by Jenkins, GitLab CI and GitHub Actions so the three run the suites the same way.
# Needs Python 3.10+ / Node 20 / Chrome on the host. The C# suite uses a local `dotnet` if there
# is one, otherwise the .NET SDK container against a ChromeDriver started here.
set -euo pipefail

suite=${1:?usage: run-suite.sh python|js|dotnet [--smoke]}
smoke=${2:-}
e2e=$(cd "$(dirname "$0")" && pwd)

case "$suite" in
python)
	cd "$e2e/python"
	[ -x .venv/bin/pytest ] || python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt
	.venv/bin/pytest ${smoke:+-m smoke} --junitxml=artifacts/junit.xml
	;;
js)
	cd "$e2e/js"
	npm ci --no-audit --no-fund
	npx mocha ${smoke:+--grep @smoke} --reporter xunit --reporter-option output=artifacts/junit.xml
	;;
dotnet)
	cd "$e2e/dotnet/ReceiptCapture.E2E"
	args=(test ${smoke:+--filter TestCategory=Smoke} --results-directory TestResults
		--logger "junit;LogFilePath=TestResults/junit.xml" --logger "trx;LogFileName=results.trx")
	if command -v dotnet > /dev/null; then
		dotnet "${args[@]}"
		exit
	fi
	# ChromeDriver from Selenium Manager's cache (the Python and JS suites download it)
	driver=$(ls -t "$HOME"/.cache/selenium/chromedriver/*/*/chromedriver 2> /dev/null | head -1)
	[ -n "$driver" ] || { echo "No ChromeDriver in ~/.cache/selenium: run the python or js suite first" >&2; exit 1; }
	mkdir -p TestResults
	"$driver" --port=9515 > TestResults/chromedriver.log 2>&1 &
	trap 'kill $! 2> /dev/null || true' EXIT
	# Mounted at the same path, so results land where CI looks and fixtures resolve
	docker run --rm --network host -v "$e2e:$e2e" -w "$PWD" \
		-u "$(id -u):$(id -g)" -e HOME=/tmp -e DOTNET_CLI_HOME=/tmp -e NUGET_PACKAGES="$e2e/.nuget/packages" \
		-e BASE_URL -e ADMIN_PASSWORD -e E2E_USER_PASSWORD -e HEADLESS -e EXTRACTION_TIMEOUT_MS \
		-e SELENIUM_REMOTE_URL=http://127.0.0.1:9515 \
		"${DOTNET_SDK_IMAGE:-mcr.microsoft.com/dotnet/sdk:9.0}" dotnet "${args[@]}"
	;;
*)
	echo "unknown suite: $suite" >&2
	exit 2
	;;
esac
