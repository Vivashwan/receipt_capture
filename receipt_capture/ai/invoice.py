"""Turns a reviewed Receipt Capture into a draft ERPNext Purchase Invoice."""

import frappe
from frappe import _
from frappe.utils import flt, get_link_to_form, getdate, nowdate


def create_purchase_invoice(receipt):
	settings = frappe.get_cached_doc("Receipt AI Settings")
	if receipt.purchase_invoice:
		frappe.throw(
			_("Purchase Invoice {0} already exists for this receipt").format(receipt.purchase_invoice)
		)
	if not settings.expense_item:
		frappe.throw(
			_("Set a Default Expense Item in {0} first").format(
				get_link_to_form("Receipt AI Settings", "Receipt AI Settings")
			)
		)
	if flt(receipt.total_amount) <= 0:
		frappe.throw(_("Total Amount must be greater than zero"))

	supplier = receipt.supplier or get_or_create_supplier(receipt.supplier_name, settings)
	company_currency = frappe.get_cached_value("Company", receipt.company, "default_currency")
	bill_date = getdate(receipt.bill_date) if receipt.bill_date else None

	pi = frappe.new_doc("Purchase Invoice")
	pi.company = receipt.company
	pi.supplier = supplier
	pi.bill_no = receipt.bill_number
	pi.bill_date = bill_date
	# Post on the receipt's date (not today), so expenses land in the right period
	pi.set_posting_time = 1
	pi.posting_date = bill_date or getdate(nowdate())
	pi.due_date = pi.posting_date
	pi.remarks = _("Created from {0} (AI receipt capture)").format(receipt.name)

	notes = []
	if receipt.currency and receipt.currency != company_currency:
		# Converting needs an exchange rate the receipt doesn't carry; leave it to the reviewer
		notes.append(
			_("Receipt currency is {0}; invoice uses company currency {1}").format(
				receipt.currency, company_currency
			)
		)

	lines = receipt.items or []
	if lines:
		for row in lines:
			pi.append(
				"items",
				{
					"item_code": row.item_code or settings.expense_item,
					"description": row.description,
					"qty": flt(row.qty) or 1,
					"rate": flt(row.rate),
				},
			)
	else:
		pi.append(
			"items",
			{
				"item_code": settings.expense_item,
				"description": receipt.supplier_name or _("Receipt {0}").format(receipt.name),
				"qty": 1,
				"rate": flt(receipt.total_amount) - flt(receipt.tax_amount),
			},
		)

	if flt(receipt.tax_amount) and settings.tax_account:
		pi.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": settings.tax_account,
				"description": _("Tax as printed on receipt"),
				"tax_amount": flt(receipt.tax_amount),
				"category": "Total",
				"add_deduct_tax": "Add",
			},
		)
	elif flt(receipt.tax_amount):
		notes.append(
			_("Receipt shows tax {0} but no Tax Account is set in Receipt AI Settings").format(
				receipt.tax_amount
			)
		)

	if notes:
		pi.remarks += "\n" + "\n".join(notes)

	pi.set_missing_values()
	pi.insert()  # draft only: an accountant reviews and submits
	attach_receipt_to(pi, receipt)

	receipt.db_set({"purchase_invoice": pi.name, "status": "Invoiced", "supplier": supplier})
	return pi


def get_or_create_supplier(vendor: str, settings) -> str:
	from receipt_capture.ai.pipeline import match_supplier

	if not vendor:
		frappe.throw(_("Vendor name is empty; choose a Supplier before creating the invoice"))
	existing = match_supplier(vendor)
	if existing:
		return existing
	if not settings.auto_create_supplier:
		frappe.throw(
			_("No Supplier named {0}; create one or enable auto-create in settings").format(
				frappe.bold(vendor)
			)
		)
	if not frappe.has_permission("Supplier", "create"):
		# e.g. an Accounts User: ERPNext lets them invoice but not add suppliers
		frappe.throw(
			_(
				"No Supplier named {0}, and you can't create suppliers. Choose an existing Supplier on the receipt, or ask a Purchase Master Manager to add it."
			).format(frappe.bold(vendor)),
			frappe.PermissionError,
		)

	supplier_group = (
		settings.supplier_group
		or frappe.db.get_single_value("Buying Settings", "supplier_group")
		or frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	)
	supplier = frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": vendor,
			"supplier_group": supplier_group,
			"supplier_type": "Company",
		}
	).insert()
	return supplier.name


def attach_receipt_to(pi, receipt) -> None:
	"""Copies the receipt image onto the invoice so auditors see the source document."""
	source = frappe.db.get_value(
		"File", {"file_url": receipt.receipt_image}, ["file_name", "file_url", "is_private"], as_dict=True
	)
	if not source:
		return
	frappe.get_doc(
		{
			"doctype": "File",
			"file_url": source.file_url,
			"file_name": source.file_name,
			"is_private": source.is_private,
			"attached_to_doctype": "Purchase Invoice",
			"attached_to_name": pi.name,
		}
	).insert(ignore_permissions=True)
