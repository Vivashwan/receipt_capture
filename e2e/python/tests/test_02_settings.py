import pytest

import config
from conftest import browser_for
from pages.settings import ReceiptAISettingsPage

browser = browser_for(config.ADMIN_USER, config.ADMIN_PASSWORD)


@pytest.mark.smoke
def test_reports_that_the_local_model_is_reachable(browser):
	settings = ReceiptAISettingsPage(browser)
	settings.open()
	model = settings.doc_value("model")

	dialog = settings.test_connection()

	assert dialog["title"] == "Connected"
	assert model in dialog["body"]
	settings.close_dialog()
