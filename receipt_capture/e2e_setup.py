"""Seeds a site for the Selenium end-to-end suites in e2e/ (idempotent).

bench --site <site> execute receipt_capture.e2e_setup.setup_site
"""

import frappe

COMPANY = "Annapurna Traders"
EXPENSE_ITEM = "Receipt Expense"
REVIEWER_EMAIL = "reviewer@example.com"
NO_ACCESS_EMAIL = "no-access@example.com"


def setup_site(password: str = "e2e-user-pass"):
	complete_setup_wizard()
	expense_item = ensure_expense_item()
	tax_account = ensure_tax_account()

	settings = frappe.get_single("Receipt AI Settings")
	settings.update(
		{
			"auto_extract_on_upload": 1,
			"auto_create_supplier": 1,
			"expense_item": expense_item,
			"tax_account": tax_account,
		}
	)
	settings.save(ignore_permissions=True)

	# An accounts user who reviews receipts (and may add new suppliers), and a user with no access to them
	ensure_user(
		REVIEWER_EMAIL,
		"Receipt Reviewer",
		["Accounts User", "Purchase User", "Purchase Master Manager"],
		password,
	)
	ensure_user(NO_ACCESS_EMAIL, "No Access", ["Stock User"], password)
	frappe.db.commit()


def complete_setup_wizard():
	if frappe.db.a_row_exists("Company"):
		return
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	year = frappe.utils.now_datetime().year
	setup_complete(
		{
			"currency": "INR",
			"full_name": "Administrator",
			"company_name": COMPANY,
			"company_abbr": "AT",
			"timezone": "Asia/Kolkata",
			"country": "India",
			"fy_start_date": f"{year}-01-01",
			"fy_end_date": f"{year}-12-31",
			"language": "english",
			"chart_of_accounts": "Standard",
			"email": "admin@example.com",
		}
	)


def ensure_expense_item() -> str:
	if not frappe.db.exists("Item", EXPENSE_ITEM):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": EXPENSE_ITEM,
				"item_name": EXPENSE_ITEM,
				"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"stock_uom": "Nos",
				"is_stock_item": 0,
				"is_purchase_item": 1,
			}
		).insert(ignore_permissions=True)
	return EXPENSE_ITEM


def ensure_tax_account() -> str:
	"""India's standard chart only has the "Duties and Taxes" group; GST needs a postable account."""
	existing = frappe.db.get_value(
		"Account", {"company": COMPANY, "account_type": "Tax", "is_group": 0}, "name"
	)
	if existing:
		return existing
	parent = frappe.db.get_value(
		"Account", {"company": COMPANY, "account_type": "Tax", "is_group": 1}, "name"
	)
	return (
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": "Input GST",
				"company": COMPANY,
				"parent_account": parent,
				"account_type": "Tax",
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def ensure_user(email: str, first_name: str, roles: list[str], password: str):
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": first_name, "send_welcome_email": 0}
		)
		user.insert(ignore_permissions=True)
	user = frappe.get_doc("User", email)
	user.add_roles(*roles)
	from frappe.utils.password import update_password

	update_password(email, password)
