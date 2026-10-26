import frappe


def before_tests():
	"""Run ERPNext's test bootstrap (company, fiscal year, defaults) when only this app's tests are run."""
	if not frappe.db.a_row_exists("Company"):
		from erpnext.setup.utils import before_tests as erpnext_before_tests

		erpnext_before_tests()
