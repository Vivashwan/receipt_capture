# Copyright (c) 2026, Vivashwan Ghosh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ReceiptAISettings(Document):
	def validate(self):
		self.ollama_url = (self.ollama_url or "").strip().rstrip("/")
		if not self.ollama_url.startswith(("http://", "https://")):
			frappe.throw(_("Ollama URL must start with http:// or https://"))
		if self.request_timeout and self.request_timeout < 10:
			frappe.throw(_("Request timeout must be at least 10 seconds; local models can be slow"))
		if self.expense_item and frappe.db.get_value("Item", self.expense_item, "is_stock_item"):
			frappe.throw(
				_("Default Expense Item must be a non-stock item (receipts are expenses, not stock)")
			)
