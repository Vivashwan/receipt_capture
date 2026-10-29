import pytest

import config
from conftest import browser_for
from pages.login import LoginPage

browser = browser_for()

pytestmark = pytest.mark.smoke


def test_rejects_a_wrong_password_and_stays_on_the_login_page(browser):
	login = LoginPage(browser)
	login.open()
	login.submit(config.ADMIN_USER, "not-the-password")

	assert "Invalid Login" in login.wait_for_error()
	assert "/login" in browser.current_url


def test_logs_in_with_valid_credentials_and_opens_the_desk(browser):
	LoginPage(browser).login_as(config.ADMIN_USER, config.ADMIN_PASSWORD)

	assert "/app" in browser.current_url
