"""Receipt photo to draft Purchase Invoice.

The fixture is a tilted, noisy photo of: RICE 320.00 / DAL 160.00 / GST 24.00 / TOTAL 504.00.
The tests run in order and share one browser: each step continues where the previous one left off.
"""

import re

import config
from conftest import browser_for
from pages.purchase_invoice import PurchaseInvoicePage
from pages.receipt_capture import ReceiptCapturePage

browser = browser_for(config.REVIEWER, config.USER_PASSWORD)
state = {}


def test_uploads_a_receipt_photo_and_queues_extraction(browser):
	receipt = ReceiptCapturePage(browser)
	state["receipt"] = receipt.upload("receipt.png")

	assert state["receipt"].startswith("RCPT-")
	assert receipt.status() == "Processing"
	assert "Reading the receipt" in receipt.headline()


def test_updates_the_open_form_live_when_the_background_job_finishes(browser):
	receipt = ReceiptCapturePage(browser)

	status = receipt.wait_for_extraction()

	assert status in ("Extracted", "Needs Review"), f"unexpected status {status}"
	receipt.wait_for_alert("Extraction finished")


def test_fills_vendor_line_items_tax_and_total_from_the_photo(browser):
	receipt = ReceiptCapturePage(browser)

	assert re.search("annapurna", receipt.doc_value("supplier_name"), re.I)
	assert receipt.doc_value("total_amount") == 504
	assert receipt.doc_value("tax_amount") == 24
	descriptions = " | ".join(line["description"].upper() for line in receipt.line_items())
	assert "RICE" in descriptions
	assert "DAL" in descriptions
	assert not re.search("TOTAL|GST", descriptions), (
		f"summary or tax rows leaked into the items: {descriptions}"
	)


def test_creates_a_draft_purchase_invoice_with_the_receipts_amounts(browser):
	ReceiptCapturePage(browser).create_purchase_invoice()

	invoice = PurchaseInvoicePage(browser)
	details = invoice.details()

	assert invoice.status() == "Draft"
	assert details["docstatus"] == 0, "invoices are left as drafts for an accountant to submit"
	assert details["grand_total"] == 504
	assert details["total_taxes"] == 24
	assert details["supplier"], "a supplier is matched or created"
	assert all(item["item_code"] == "Receipt Expense" for item in details["items"])


def test_marks_the_receipt_invoiced_and_locks_it(browser):
	receipt = ReceiptCapturePage(browser)
	receipt.open(state["receipt"])

	assert receipt.status() == "Invoiced"
	assert receipt.doc_value("purchase_invoice")
	assert receipt.has_button("Open Purchase Invoice")
	assert not receipt.has_button("Create Purchase Invoice"), "can't invoice twice"
	assert not receipt.has_button("Re-run Extraction"), "can't overwrite an invoiced receipt"
