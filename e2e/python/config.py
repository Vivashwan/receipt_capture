"""Everything the suite needs from the environment, with defaults matching docker-compose.yml."""

import os
from pathlib import Path

BASE_URL = os.environ.get("BASE_URL", "http://erp.localhost:8080").rstrip("/")
ADMIN_USER = os.environ.get("ADMIN_USER", "Administrator")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
USER_PASSWORD = os.environ.get("E2E_USER_PASSWORD", "e2e-user-pass")
REVIEWER = "reviewer@example.com"
NO_ACCESS_USER = "no-access@example.com"
HEADLESS = os.environ.get("HEADLESS") != "0"
# Remote Selenium Grid / chromedriver URL; local Chrome via Selenium Manager when unset
REMOTE_URL = os.environ.get("SELENIUM_REMOTE_URL")
# OCR + a CPU-only model can take a while on a cold start
EXTRACTION_TIMEOUT = int(os.environ.get("EXTRACTION_TIMEOUT_MS", "240000")) / 1000
ARTIFACTS_DIR = Path(os.environ.get("ARTIFACTS_DIR", "artifacts"))
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
