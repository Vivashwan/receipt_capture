"""Client for a local Ollama server.

Runs the model on your own infrastructure, so receipt contents never leave it.
Ollama's `format` option takes a JSON schema and constrains generation to it,
which makes small local models far more reliable at returning structured data.
"""

from __future__ import annotations

import json

import requests

from receipt_capture.ai.extraction import RECEIPT_SCHEMA

SYSTEM_PROMPT = """You extract data from OCR text of shop receipts and bills.
Return JSON matching the schema. Rules:
- vendor: the shop or company that issued the receipt (usually the first lines).
- bill_date: the date printed on the receipt, exactly as written.
- line_items: each purchased item with its amount; skip subtotal, tax, discount and total lines.
- tax_amount: total tax (GST/CGST+SGST/VAT) if shown, else 0.
- total_amount: the final amount payable.
- Use plain numbers without currency symbols or thousands separators.
- If a field is not present, use an empty string (or 0 for numbers). Never invent values."""


class LLMError(RuntimeError):
	"""Ollama was unreachable, timed out, or returned an unexpected response."""


class OllamaClient:
	def __init__(self, base_url: str, model: str, timeout: int = 120):
		self.base_url = base_url.rstrip("/")
		self.model = model
		self.timeout = timeout

	def extract_receipt(self, ocr_text: str) -> dict:
		"""Returns the model's JSON (not yet validated; see extraction.parse_llm_output)."""
		payload = {
			"model": self.model,
			"stream": False,
			"format": RECEIPT_SCHEMA,
			# Deterministic output: the same receipt should always extract the same way
			"options": {"temperature": 0},
			"messages": [
				{"role": "system", "content": SYSTEM_PROMPT},
				{"role": "user", "content": f"Receipt OCR text:\n\n{ocr_text[:6000]}"},
			],
		}
		try:
			response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
		except requests.Timeout as exc:
			raise LLMError(f"Ollama did not respond within {self.timeout}s") from exc
		except requests.RequestException as exc:
			raise LLMError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc

		if response.status_code == 404:
			raise LLMError(
				f"Model {self.model!r} is not pulled on the Ollama server (run: ollama pull {self.model})"
			)
		if not response.ok:
			raise LLMError(f"Ollama returned HTTP {response.status_code}: {response.text[:200]}")

		content = (response.json().get("message") or {}).get("content", "")
		try:
			return json.loads(content)
		except json.JSONDecodeError as exc:
			raise LLMError(f"Model returned non-JSON content: {content[:200]!r}") from exc

	def health(self) -> dict:
		"""Checks the server is up and the configured model is available."""
		try:
			response = requests.get(f"{self.base_url}/api/tags", timeout=10)
			response.raise_for_status()
		except requests.RequestException as exc:
			return {"ok": False, "error": f"Ollama unreachable at {self.base_url}: {exc}"}

		models = [m.get("name", "") for m in response.json().get("models", [])]
		available = any(name == self.model or name.split(":")[0] == self.model for name in models)
		return {
			"ok": available,
			"models": models,
			"error": None if available else f"Model {self.model!r} not pulled; available: {models}",
		}
