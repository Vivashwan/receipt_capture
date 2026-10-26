# Copyright (c) 2026, Vivashwan Ghosh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

# Statuses from which a receipt may be (re-)sent to the model
EXTRACTABLE = ("Pending", "Extracted", "Needs Review", "Failed")
INVOICEABLE = ("Extracted", "Needs Review")


class ReceiptCapture(Document):
	def validate(self):
		self.calculate_totals()

	def calculate_totals(self):
		for row in self.items:
			row.qty = flt(row.qty) or 1
			# Keep amount and rate consistent when the user edits one of them
			if not flt(row.amount) and flt(row.rate):
				row.amount = flt(row.qty * row.rate, row.precision("amount"))
			elif flt(row.amount) and not flt(row.rate):
				row.rate = flt(row.amount / row.qty, row.precision("rate"))
		self.lines_total = flt(sum(flt(row.amount) for row in self.items), self.precision("lines_total"))

	def after_insert(self):
		settings = frappe.get_cached_doc("Receipt AI Settings")
		if settings.auto_extract_on_upload and self.receipt_image:
			self.queue_extraction()

	def on_trash(self):
		if self.purchase_invoice and frappe.db.exists("Purchase Invoice", self.purchase_invoice):
			frappe.throw(
				_("Cannot delete: Purchase Invoice {0} was created from this receipt").format(
					frappe.bold(self.purchase_invoice)
				)
			)

	@frappe.whitelist()
	def extract(self):
		"""Runs (or re-runs) OCR + LLM extraction in the background."""
		self.check_permission("write")
		if self.status not in EXTRACTABLE:
			frappe.throw(
				_("A receipt in status {0} can't be extracted again").format(frappe.bold(self.status))
			)
		self.queue_extraction()

	def queue_extraction(self):
		self.db_set({"status": "Processing", "error_message": None})
		frappe.enqueue(
			"receipt_capture.ai.pipeline.process_receipt",
			queue="long",
			timeout=900,
			receipt_name=self.name,
			# Only start once this transaction commits, so the worker sees the new row
			enqueue_after_commit=True,
			job_id=f"receipt_capture::{self.name}",
			deduplicate=True,
		)

	@frappe.whitelist()
	def make_purchase_invoice(self):
		"""Creates a draft Purchase Invoice from the reviewed receipt and returns its name."""
		self.check_permission("write")
		if self.status not in INVOICEABLE:
			frappe.throw(
				_("Only extracted receipts can be invoiced (current status: {0})").format(self.status)
			)

		from receipt_capture.ai.invoice import create_purchase_invoice

		return create_purchase_invoice(self).name
