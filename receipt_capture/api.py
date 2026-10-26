import frappe

from receipt_capture.ai.pipeline import get_client


@frappe.whitelist()
def check_ollama() -> dict:
	"""Used by the settings form's "Test Ollama Connection" button."""
	frappe.only_for("System Manager")
	return get_client().health()
