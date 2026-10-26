# Copyright (c) 2026, Vivashwan Ghosh and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, getdate, now_datetime

from receipt_capture.ai import ocr, pipeline
from receipt_capture.ai.llm import LLMError
from receipt_capture.ai.tests.test_ocr import make_receipt

OCR_TEXT = (
	"ANNAPURNA STORES\nBILL NO B-1042\nDATE 12/03/2026\nRICE 5KG 320.00\nDAL 160.00\nGST 24.00\nTOTAL 504.00"
)
LLM_RESULT = {
	"vendor": "Annapurna Stores",
	"bill_number": "B-1042",
	"bill_date": "12/03/2026",
	"currency": "INR",
	"line_items": [
		{"description": "Rice 5kg", "quantity": 1, "rate": 320, "amount": 320},
		{"description": "Dal", "quantity": 2, "rate": 80, "amount": 160},
	],
	"tax_amount": 24,
	"total_amount": 504,
}
EXPENSE_ITEM = "_Test Receipt Expense"

# These tests build their own records on the company created by ERPNext's setup
# (see tests_setup.before_tests). Skip Frappe's automatic test-record generation
# for linked doctypes: through Purchase Invoice it reaches doctypes from apps that
# aren't installed (e.g. Payment Gateway from the payments app).
test_ignore = ["Company", "Supplier", "Purchase Invoice", "Currency", "Item", "Account", "Supplier Group"]


def ensure_expense_item():
	if not frappe.db.exists("Item", EXPENSE_ITEM):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": EXPENSE_ITEM,
				"item_name": "Receipt Expense",
				"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"stock_uom": "Nos",
				"is_stock_item": 0,
				"is_purchase_item": 1,
			}
		).insert()
	return EXPENSE_ITEM


class TestReceiptCapture(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Tests change the settings; remember them so a developer's site is left as it was
		cls.original_settings = frappe.get_single("Receipt AI Settings").as_dict(no_default_fields=True)
		cls.company = frappe.db.get_value("Company", {}, "name")
		cls.image_url = (
			frappe.get_doc(
				{"doctype": "File", "file_name": "receipt.png", "content": make_receipt(), "is_private": 1}
			)
			.insert()
			.file_url
		)

	@classmethod
	def tearDownClass(cls):
		settings = frappe.get_single("Receipt AI Settings")
		settings.update(cls.original_settings)
		settings.save()
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		settings = frappe.get_single("Receipt AI Settings")
		settings.update(
			{
				"ollama_url": "http://ollama:11434",
				"model": "test-model",
				"auto_extract_on_upload": 0,
				"auto_create_supplier": 1,
				"expense_item": ensure_expense_item(),
				"tax_account": None,
			}
		)
		settings.save()

	def make_receipt(self, **values):
		return frappe.get_doc(
			{"doctype": "Receipt Capture", "company": self.company, "receipt_image": self.image_url, **values}
		).insert()

	def extract(self, receipt, llm_result=None, ocr_error=None, llm_error=None):
		"""Runs the real pipeline with OCR and the model replaced by fixed results."""
		ocr_patch = patch.object(pipeline.ocr, "extract_text", side_effect=ocr_error, return_value=OCR_TEXT)
		llm_patch = patch.object(
			pipeline.OllamaClient,
			"extract_receipt",
			side_effect=llm_error,
			return_value=llm_result or LLM_RESULT,
		)
		with ocr_patch, llm_patch:
			pipeline.process_receipt(receipt.name)
		receipt.reload()
		return receipt

	# ---- document behaviour ----

	def test_totals_are_calculated_from_lines(self):
		receipt = self.make_receipt(
			items=[
				{"description": "Tea", "qty": 2, "rate": 15},
				{"description": "Snack", "qty": 1, "amount": 40},
			]
		)

		self.assertEqual([row.amount for row in receipt.items], [30, 40])
		self.assertEqual(receipt.items[1].rate, 40)
		self.assertEqual(receipt.lines_total, 70)

	def test_upload_queues_extraction_when_enabled(self):
		frappe.db.set_single_value("Receipt AI Settings", "auto_extract_on_upload", 1)
		frappe.clear_document_cache("Receipt AI Settings", "Receipt AI Settings")

		with patch("frappe.enqueue") as enqueue:
			receipt = self.make_receipt()

		enqueue.assert_called_once()
		self.assertEqual(enqueue.call_args.args[0], "receipt_capture.ai.pipeline.process_receipt")
		self.assertEqual(enqueue.call_args.kwargs["receipt_name"], receipt.name)
		self.assertEqual(frappe.db.get_value("Receipt Capture", receipt.name, "status"), "Processing")

	def test_upload_does_not_queue_when_disabled(self):
		with patch("frappe.enqueue") as enqueue:
			receipt = self.make_receipt()

		enqueue.assert_not_called()
		self.assertEqual(receipt.status, "Pending")

	# ---- extraction pipeline ----

	def test_extraction_fills_the_document(self):
		receipt = self.extract(self.make_receipt())

		self.assertEqual(receipt.status, "Extracted")
		self.assertEqual(receipt.supplier_name, "Annapurna Stores")
		self.assertEqual(receipt.bill_number, "B-1042")
		self.assertEqual(getdate(receipt.bill_date), getdate("2026-03-12"))
		self.assertEqual(
			[(row.description, row.amount) for row in receipt.items], [("Rice 5kg", 320), ("Dal", 160)]
		)
		self.assertEqual((receipt.lines_total, receipt.tax_amount, receipt.total_amount), (480, 24, 504))
		self.assertEqual(receipt.ocr_text, OCR_TEXT)
		self.assertEqual(receipt.model_used, "test-model")
		self.assertIsNotNone(receipt.processing_time)

	def test_extraction_matches_an_existing_supplier(self):
		# An earlier test may already have auto-created this supplier when invoicing
		supplier = frappe.db.get_value("Supplier", {"supplier_name": "Annapurna Stores"}) or (
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": "Annapurna Stores",
					"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
				}
			)
			.insert()
			.name
		)

		receipt = self.extract(self.make_receipt())

		self.assertEqual(receipt.supplier, supplier)

	def test_mismatched_totals_need_review(self):
		receipt = self.extract(self.make_receipt(), llm_result={**LLM_RESULT, "total_amount": 900})

		self.assertEqual(receipt.status, "Needs Review")
		self.assertIn("do not match", receipt.review_notes)

	def test_ocr_and_model_failures_are_recorded(self):
		failed_ocr = self.extract(self.make_receipt(), ocr_error=ocr.OCRError("No readable text found"))
		self.assertEqual(failed_ocr.status, "Failed")
		self.assertEqual(failed_ocr.error_message, "No readable text found")

		failed_llm = self.extract(self.make_receipt(), llm_error=LLMError("Could not reach Ollama"))
		self.assertEqual(failed_llm.status, "Failed")
		self.assertIn("Could not reach Ollama", failed_llm.error_message)

	def test_rerunning_replaces_previous_lines(self):
		receipt = self.extract(self.make_receipt())
		receipt = self.extract(
			receipt, llm_result={**LLM_RESULT, "line_items": [{"description": "Combo", "amount": 480}]}
		)

		self.assertEqual([row.description for row in receipt.items], ["Combo"])

	def test_stuck_receipts_are_released(self):
		receipt = self.make_receipt()
		frappe.db.set_value(
			"Receipt Capture",
			receipt.name,
			{"status": "Processing", "modified": add_to_date(now_datetime(), hours=-2)},
			update_modified=False,
		)

		pipeline.fail_stuck_receipts()

		self.assertEqual(frappe.db.get_value("Receipt Capture", receipt.name, "status"), "Failed")

	# ---- invoicing ----

	def test_creates_a_draft_purchase_invoice(self):
		receipt = self.extract(self.make_receipt())

		pi = frappe.get_doc("Purchase Invoice", receipt.make_purchase_invoice())
		receipt.reload()

		self.assertEqual(pi.docstatus, 0, "invoice must stay a draft for an accountant to review")
		self.assertEqual(pi.company, self.company)
		self.assertEqual(frappe.db.get_value("Supplier", pi.supplier, "supplier_name"), "Annapurna Stores")
		self.assertEqual(getdate(pi.posting_date), getdate("2026-03-12"))
		self.assertEqual(pi.bill_no, "B-1042")
		self.assertEqual(
			[(row.item_code, row.qty, row.rate) for row in pi.items],
			[(EXPENSE_ITEM, 1, 320), (EXPENSE_ITEM, 2, 80)],
		)
		self.assertEqual(pi.net_total, 480)
		self.assertIn("no Tax Account", pi.remarks)
		self.assertEqual(
			(receipt.status, receipt.purchase_invoice, receipt.supplier), ("Invoiced", pi.name, pi.supplier)
		)
		self.assertTrue(
			frappe.db.exists("File", {"attached_to_doctype": "Purchase Invoice", "attached_to_name": pi.name})
		)

		with self.assertRaises(frappe.ValidationError):
			receipt.make_purchase_invoice()

	def test_adds_tax_row_when_tax_account_is_set(self):
		tax_account = frappe.db.get_value(
			"Account", {"company": self.company, "account_type": "Tax", "is_group": 0}, "name"
		)
		if not tax_account:
			self.skipTest("test company has no tax account")
		frappe.db.set_single_value("Receipt AI Settings", "tax_account", tax_account)
		frappe.clear_document_cache("Receipt AI Settings", "Receipt AI Settings")
		receipt = self.extract(self.make_receipt())

		pi = frappe.get_doc("Purchase Invoice", receipt.make_purchase_invoice())

		self.assertEqual([(row.account_head, row.tax_amount) for row in pi.taxes], [(tax_account, 24)])
		self.assertEqual(pi.grand_total, 504)

	def test_only_extracted_receipts_can_be_invoiced(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_receipt().make_purchase_invoice()

	def test_invoiced_receipts_cannot_be_deleted_or_re_extracted(self):
		receipt = self.extract(self.make_receipt())
		receipt.make_purchase_invoice()
		receipt.reload()

		with self.assertRaises(frappe.ValidationError):
			receipt.extract()
		with self.assertRaises(frappe.ValidationError):
			receipt.delete()

	# ---- report and settings ----

	def test_summary_report_aggregates_by_supplier(self):
		from receipt_capture.receipt_capture.report.receipt_capture_summary.receipt_capture_summary import (
			execute,
		)

		receipt = self.extract(self.make_receipt())
		receipt.make_purchase_invoice()
		self.extract(self.make_receipt())

		_columns, data, _message, chart, summary = execute({"company": self.company})

		row = next(r for r in data if r.supplier_name == "Annapurna Stores")
		self.assertGreaterEqual(row.receipts, 2)
		self.assertGreaterEqual(row.invoiced, 1)
		self.assertGreater(row.pending_amount, 0)
		self.assertTrue(chart and summary)

	def test_settings_validation(self):
		settings = frappe.get_single("Receipt AI Settings")
		settings.ollama_url = "ollama:11434"
		with self.assertRaises(frappe.ValidationError):
			settings.save()
