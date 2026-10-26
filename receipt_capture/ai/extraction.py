"""Turns raw LLM output into a clean, validated receipt.

LLMs return numbers as "₹1,234.50", dates as "12/03/2026" or "12 Mar 26", and
totals that don't always match their own line items. Everything here is pure
Python (no Frappe), so it can be unit-tested without a site.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime

# JSON schema passed to Ollama's `format` option: the model must return exactly this shape.
RECEIPT_SCHEMA = {
	"type": "object",
	"properties": {
		"vendor": {"type": "string"},
		"bill_number": {"type": "string"},
		"bill_date": {"type": "string"},
		"currency": {"type": "string"},
		"line_items": {
			"type": "array",
			"items": {
				"type": "object",
				"properties": {
					"description": {"type": "string"},
					"quantity": {"type": "number"},
					"rate": {"type": "number"},
					"amount": {"type": "number"},
				},
				"required": ["description", "amount"],
			},
		},
		"tax_amount": {"type": "number"},
		"total_amount": {"type": "number"},
	},
	"required": ["vendor", "bill_date", "line_items", "total_amount"],
}

# Totals may legitimately differ by rounding (e.g. "round off" lines on Indian bills)
TOTAL_TOLERANCE = 1.0

# Small models often return a receipt's summary rows as purchased items. Anchored at the
# start of the description so real items like "Taxi fare" are kept. Discounts are kept as
# lines because they change the amount payable.
SUMMARY_LINE = re.compile(
	r"^\s*(sub\s*-?\s*total|grand\s*total|total|net\s*(amount|total)|amount\s*(due|payable)|balance|"
	r"round(ing)?\s*off|change|cash|card|paid)\b",
	re.IGNORECASE,
)
TAX_LINE = re.compile(r"^\s*(gst|cgst|sgst|igst|utgst|vat|tax|cess|service\s*tax)\b", re.IGNORECASE)

_CURRENCY_SYMBOLS = {
	"₹": "INR",
	"rs": "INR",
	"inr": "INR",
	"$": "USD",
	"usd": "USD",
	"€": "EUR",
	"eur": "EUR",
	"£": "GBP",
	"gbp": "GBP",
}
_DATE_FORMATS = (
	"%Y-%m-%d",
	"%d/%m/%Y",
	"%d-%m-%Y",
	"%d.%m.%Y",
	"%d/%m/%y",
	"%d-%m-%y",
	"%d %b %Y",
	"%d %B %Y",
	"%d %b %y",
	"%b %d, %Y",
	"%B %d, %Y",
)


@dataclass
class ReceiptLine:
	description: str
	qty: float
	rate: float
	amount: float


@dataclass
class ExtractedReceipt:
	vendor: str
	bill_number: str
	bill_date: date | None
	currency: str | None
	lines: list[ReceiptLine]
	tax_amount: float
	total_amount: float
	warnings: list[str] = field(default_factory=list)

	@property
	def lines_total(self) -> float:
		return round(sum(line.amount for line in self.lines), 2)


class ExtractionError(ValueError):
	"""The model's output could not be turned into a usable receipt."""


def parse_amount(value) -> float | None:
	"""'₹1,234.50' -> 1234.5, '(12.00)' -> -12.0, '' / None / 'n/a' -> None."""
	if value is None or isinstance(value, bool):
		return None
	if isinstance(value, (int, float)):
		return round(float(value), 2)

	text = str(value).strip()
	negative = (text.startswith("(") and text.endswith(")")) or text.startswith("-")
	# Take the number itself, so a currency prefix like "Rs." can't contribute a stray "."
	match = re.search(r"\d[\d,]*(?:\.\d+)?", text)
	if not match or re.search(r"\d\.\d+\.\d", text):
		return None  # no digits, or malformed like "1.2.3"
	amount = round(float(match.group().replace(",", "")), 2)
	return -amount if negative else amount


def parse_date(value) -> date | None:
	"""Parses common receipt date formats. Ambiguous numeric dates are read day-first (Indian style)."""
	if not value:
		return None
	if isinstance(value, date):
		return value

	text = re.sub(r"\s+", " ", str(value).strip().replace(",", ", ")).replace(" ,", ",")
	text = text.replace(",,", ",")
	for fmt in _DATE_FORMATS:
		try:
			return datetime.strptime(text, fmt).date()
		except ValueError:
			continue
	return None


def amounts_in_text(text: str) -> set[float]:
	"""All numbers printed in the OCR text, e.g. 'Rs.1,234.50' -> 1234.5."""
	return {round(float(match.replace(",", "")), 2) for match in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def detect_currency(value, ocr_text: str = "") -> str | None:
	"""Maps a symbol/code from the model (or, failing that, the OCR text) to an ISO code."""
	for candidate in (value, ocr_text):
		if not candidate:
			continue
		lowered = str(candidate).lower()
		if re.fullmatch(r"[a-z]{3}", lowered.strip()):
			return lowered.strip().upper()
		for symbol, code in _CURRENCY_SYMBOLS.items():
			if symbol in lowered:
				return code
	return None


def parse_llm_output(raw, ocr_text: str = "") -> ExtractedReceipt:
	"""Validates and normalises the model's JSON. Raises ExtractionError if unusable."""
	if isinstance(raw, str):
		try:
			data = json.loads(raw)
		except json.JSONDecodeError as exc:
			raise ExtractionError(f"Model did not return valid JSON: {exc}") from exc
	else:
		data = raw
	if not isinstance(data, dict):
		raise ExtractionError("Model output is not a JSON object")

	warnings: list[str] = []
	lines = []
	tax_from_lines = 0.0
	for item in data.get("line_items") or []:
		if not isinstance(item, dict):
			continue
		description = str(item.get("description") or "").strip()
		qty = parse_amount(item.get("quantity")) or 1.0
		rate = parse_amount(item.get("rate"))
		amount = parse_amount(item.get("amount"))
		if amount is None and rate is not None:
			amount = round(qty * rate, 2)
		if amount is None or not description:
			continue  # unusable line
		if TAX_LINE.match(description):
			tax_from_lines += amount
			continue
		if SUMMARY_LINE.match(description):
			continue
		if rate is None:
			rate = round(amount / qty, 2) if qty else amount
		lines.append(ReceiptLine(description=description[:140], qty=qty, rate=rate, amount=amount))

	tax = parse_amount(data.get("tax_amount")) or round(tax_from_lines, 2)
	total = parse_amount(data.get("total_amount"))
	lines_total = round(sum(line.amount for line in lines), 2)

	if total is None:
		if not lines:
			raise ExtractionError("No total and no line items found on the receipt")
		total = round(lines_total + tax, 2)
		warnings.append("Total was missing; computed from line items")
	elif lines and abs(lines_total + tax - total) > TOTAL_TOLERANCE:
		warnings.append(
			f"Line items ({lines_total:.2f}) + tax ({tax:.2f}) do not match total ({total:.2f}); please review"
		)

	if total <= 0:
		raise ExtractionError(f"Total must be positive, got {total}")

	# Grounding check: every amount should be printed somewhere on the receipt
	if ocr_text:
		printed = amounts_in_text(ocr_text)
		for line in lines:
			if round(line.amount, 2) not in printed:
				warnings.append(
					f"Amount {line.amount:.2f} for {line.description!r} was not found on the receipt; it may be misread"
				)
		if round(total, 2) not in printed and not any("computed from line items" in w for w in warnings):
			warnings.append(f"Total {total:.2f} was not found on the receipt; it may be misread")

	bill_date = parse_date(data.get("bill_date"))
	if data.get("bill_date") and bill_date is None:
		warnings.append(f"Could not read bill date {data.get('bill_date')!r}")
	if bill_date and bill_date > date.today():
		warnings.append(f"Bill date {bill_date.isoformat()} is in the future; please review")

	vendor = str(data.get("vendor") or "").strip()
	if not vendor:
		warnings.append("Vendor name not found")

	return ExtractedReceipt(
		vendor=vendor[:140],
		bill_number=str(data.get("bill_number") or "").strip()[:140],
		bill_date=bill_date,
		currency=detect_currency(data.get("currency"), ocr_text),
		lines=lines,
		tax_amount=tax,
		total_amount=total,
		warnings=warnings,
	)
