"""Background job: receipt image -> OCR -> local LLM -> validated fields on the document."""

import json
import time

import frappe
from frappe.utils import add_to_date, now_datetime

from receipt_capture.ai import ocr
from receipt_capture.ai.extraction import ExtractedReceipt, ExtractionError, parse_llm_output
from receipt_capture.ai.llm import LLMError, OllamaClient

REALTIME_EVENT = "receipt_capture_update"
STUCK_AFTER_MINUTES = 30


def get_client(settings=None) -> OllamaClient:
	settings = settings or frappe.get_cached_doc("Receipt AI Settings")
	return OllamaClient(settings.ollama_url, settings.model, timeout=settings.request_timeout or 180)


def read_attachment(file_url: str) -> bytes:
	"""Reads an attached file's bytes, whether it's public or private."""
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		raise ocr.OCRError(f"Attachment {file_url} was not found")
	return frappe.get_doc("File", file_name).get_content()


def process_receipt(receipt_name: str) -> None:
	"""Entry point for the background worker (queued by ReceiptCapture.queue_extraction)."""
	doc = frappe.get_doc("Receipt Capture", receipt_name)
	settings = frappe.get_cached_doc("Receipt AI Settings")
	started = time.monotonic()
	doc.model_used = settings.model

	try:
		text = ocr.extract_text(read_attachment(doc.receipt_image), lang=settings.ocr_language or "eng")
		doc.ocr_text = text
		raw = get_client(settings).extract_receipt(text)
		doc.llm_response = json.dumps(raw, indent=2, ensure_ascii=False)
		receipt = parse_llm_output(raw, ocr_text=text)
		apply_extraction(doc, receipt)
		doc.status = "Needs Review" if receipt.warnings else "Extracted"
		doc.error_message = None
	except (ocr.OCRError, LLMError, ExtractionError) as exc:
		# Expected failures: tell the user what to fix
		doc.status = "Failed"
		doc.error_message = str(exc)
	except Exception:
		doc.status = "Failed"
		doc.error_message = "Unexpected error during extraction; see Error Log"
		frappe.log_error(title=f"Receipt extraction failed: {receipt_name}")

	doc.processing_time = round(time.monotonic() - started, 1)
	doc.flags.ignore_permissions = True  # runs as the worker, not the uploading user
	doc.save()
	frappe.db.commit()

	frappe.publish_realtime(
		REALTIME_EVENT,
		{"name": doc.name, "status": doc.status},
		doctype=doc.doctype,
		docname=doc.name,
		after_commit=True,
	)


def apply_extraction(doc, receipt: ExtractedReceipt) -> None:
	"""Copies a validated extraction onto the document, replacing any previous result."""
	doc.supplier_name = receipt.vendor
	doc.supplier = doc.supplier or match_supplier(receipt.vendor)
	doc.bill_number = receipt.bill_number
	doc.bill_date = receipt.bill_date
	if receipt.currency and frappe.db.exists("Currency", receipt.currency):
		doc.currency = receipt.currency
	doc.tax_amount = receipt.tax_amount
	doc.total_amount = receipt.total_amount
	doc.review_notes = "\n".join(f"• {warning}" for warning in receipt.warnings) or None

	doc.set("items", [])
	for line in receipt.lines:
		doc.append(
			"items",
			{"description": line.description, "qty": line.qty, "rate": line.rate, "amount": line.amount},
		)


def match_supplier(vendor: str) -> str | None:
	"""Finds an existing Supplier: exact name first, then a case-insensitive prefix match."""
	if not vendor:
		return None
	exact = frappe.db.get_value("Supplier", {"supplier_name": vendor, "disabled": 0}, "name")
	if exact:
		return exact
	candidates = frappe.get_all(
		"Supplier",
		filters={"supplier_name": ["like", f"{vendor[:20]}%"], "disabled": 0},
		pluck="name",
		limit=2,
	)
	# Only accept an unambiguous match; otherwise let the user choose
	return candidates[0] if len(candidates) == 1 else None


def fail_stuck_receipts() -> None:
	"""Hourly: a worker crash can leave receipts in Processing forever; mark them Failed so they can be retried."""
	cutoff = add_to_date(now_datetime(), minutes=-STUCK_AFTER_MINUTES)
	for name in frappe.get_all(
		"Receipt Capture", filters={"status": "Processing", "modified": ["<", cutoff]}, pluck="name"
	):
		frappe.db.set_value(
			"Receipt Capture",
			name,
			{
				"status": "Failed",
				"error_message": f"Extraction did not finish within {STUCK_AFTER_MINUTES} minutes",
			},
		)
