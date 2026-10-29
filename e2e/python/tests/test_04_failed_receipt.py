"""An unreadable receipt: the user is told why, then keys the lines in by hand."""

import config
from conftest import browser_for
from pages.receipt_capture import ReceiptCapturePage

browser = browser_for(config.REVIEWER, config.USER_PASSWORD)


def test_fails_with_a_reason_the_user_can_act_on(browser):
	receipt = ReceiptCapturePage(browser)
	receipt.upload("blank.png")

	assert receipt.wait_for_extraction() == "Failed"
	assert "No readable text" in receipt.headline()
	assert receipt.has_button("Re-run Extraction")
	assert not receipt.has_button("Create Purchase Invoice")


def test_lets_the_user_key_in_lines_by_hand_with_totals_kept_in_sync(browser):
	receipt = ReceiptCapturePage(browser)

	first = receipt.add_row()
	receipt.set_cell(first, "description", "Printer paper")
	receipt.set_cell(first, "qty", 2)
	receipt.set_cell(first, "rate", 150)
	second = receipt.add_row()
	receipt.set_cell(second, "description", "Courier")
	receipt.set_cell(second, "rate", 60)

	assert receipt.doc_value("lines_total") == 360
	assert [line["description"] for line in receipt.line_items()] == ["Printer paper", "Courier"]


def test_warns_when_items_and_tax_dont_add_up_to_the_total(browser):
	receipt = ReceiptCapturePage(browser)

	receipt.set_field("tax_amount", 18)
	receipt.set_field("total_amount", 500)

	receipt.wait_for_alert("don't match the total")


def test_saves_the_manual_corrections(browser):
	receipt = ReceiptCapturePage(browser)
	receipt.set_field("total_amount", 378)
	receipt.save()

	receipt.open(receipt.name())
	assert receipt.doc_value("lines_total") == 360
	assert receipt.doc_value("total_amount") == 378
	assert receipt.row_count() == 2
