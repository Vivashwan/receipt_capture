import pytest

import config
from conftest import browser_for
from pages.desk import DeskPage
from pages.settings import TEST_CONNECTION, ReceiptAISettingsPage

reviewer = browser_for(config.REVIEWER, config.USER_PASSWORD)
no_access = browser_for(config.NO_ACCESS_USER, config.USER_PASSWORD)


@pytest.fixture
def browser(request):
	# Each test names the user it runs as; the failure hook finds the driver under "browser"
	return request.getfixturevalue(request.param)


@pytest.mark.parametrize("browser", ["reviewer"], indirect=True)
def test_an_accounts_user_can_read_the_ai_settings_but_not_test_the_connection(browser):
	settings = ReceiptAISettingsPage(browser)
	settings.open()

	assert settings.doc_value("model")
	assert not settings.has_button(TEST_CONNECTION)


@pytest.mark.parametrize("browser", ["no_access"], indirect=True)
def test_a_user_without_an_accounts_role_is_not_shown_the_receipt_list(browser):
	page = DeskPage(browser)
	page.goto("receipt-capture")

	assert page.dialog()["title"] == "Not permitted"
	assert not page.is_present(".list-row")
