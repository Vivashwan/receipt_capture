import frappe


def after_install():
	"""Persist default settings so workers and CLI commands see them before anyone opens the form."""
	configure_ollama()


def configure_ollama(url: str | None = None, model: str | None = None):
	"""Point the app at an Ollama server. Used by docker compose:

	bench --site <site> execute receipt_capture.install.configure_ollama --kwargs "{'model': 'qwen2.5:1.5b'}"
	"""
	settings = frappe.get_single("Receipt AI Settings")
	settings.ollama_url = url or settings.ollama_url or "http://ollama:11434"
	settings.model = model or settings.model or "qwen2.5:1.5b"
	settings.request_timeout = settings.request_timeout or 180
	settings.ocr_language = settings.ocr_language or "eng"
	settings.save(ignore_permissions=True)
	frappe.db.commit()
