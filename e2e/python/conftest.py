import re
import sys
from pathlib import Path

import pytest
from selenium import webdriver

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from pages.login import LoginPage


def create_driver() -> webdriver.Remote:
	options = webdriver.ChromeOptions()
	options.add_argument("--window-size=1440,1000")
	options.add_argument("--disable-dev-shm-usage")
	# Keep the browser console, saved on failure (realtime and JS errors only show up there)
	options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
	if config.HEADLESS:
		options.add_argument("--headless=new")

	if config.REMOTE_URL:
		driver = webdriver.Remote(command_executor=config.REMOTE_URL, options=options)
	else:
		driver = webdriver.Chrome(options=options)
	# Explicit waits only: an implicit wait would slow down every "element is absent" check
	driver.implicitly_wait(0)
	driver.set_page_load_timeout(60)
	driver.set_script_timeout(30)
	return driver


def browser_for(user: str | None = None, password: str | None = None):
	"""A module-scoped browser, logged in as `user` when given (one browser per test file)."""

	@pytest.fixture(scope="module")
	def browser():
		driver = create_driver()
		try:
			if user:
				LoginPage(driver).login_as(user, password)
			yield driver
		finally:
			driver.quit()

	return browser


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
	# On any failure save a screenshot and the page HTML, so CI shows what the browser saw
	report = yield
	driver = item.funcargs.get("browser") if hasattr(item, "funcargs") else None
	if report.failed and report.when == "call" and driver:
		config.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
		name = re.sub(r"[^a-z0-9]+", "-", item.nodeid, flags=re.I)[:120]
		try:
			driver.save_screenshot(str(config.ARTIFACTS_DIR / f"{name}.png"))
			(config.ARTIFACTS_DIR / f"{name}.html").write_text(driver.page_source, encoding="utf-8")
			console = "\n".join(f"{e['level']} {e['message']}" for e in driver.get_log("browser"))
			(config.ARTIFACTS_DIR / f"{name}.console.log").write_text(console, encoding="utf-8")
		except Exception as error:
			print(f"Could not capture failure artifacts: {error}", file=sys.stderr)
	return report
