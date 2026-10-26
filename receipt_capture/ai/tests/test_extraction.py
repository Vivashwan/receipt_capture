import json
import unittest
from datetime import date, timedelta

from receipt_capture.ai.extraction import (
	ExtractionError,
	detect_currency,
	parse_amount,
	parse_date,
	parse_llm_output,
)


class TestParseAmount(unittest.TestCase):
	def test_plain_and_formatted_numbers(self):
		self.assertEqual(parse_amount(245), 245.0)
		self.assertEqual(parse_amount("245.5"), 245.5)
		self.assertEqual(parse_amount("₹1,234.50"), 1234.5)
		self.assertEqual(parse_amount("Rs. 12,34,567.00"), 1234567.0)  # Indian digit grouping
		self.assertEqual(parse_amount("$ 9.999"), 10.0)

	def test_negatives(self):
		self.assertEqual(parse_amount("(12.00)"), -12.0)
		self.assertEqual(parse_amount("-5"), -5.0)

	def test_unusable_values(self):
		for value in (None, "", "n/a", "1.2.3", True):
			self.assertIsNone(parse_amount(value), value)


class TestParseDate(unittest.TestCase):
	def test_iso_and_day_first_formats(self):
		self.assertEqual(parse_date("2026-03-12"), date(2026, 3, 12))
		# Ambiguous numeric dates are read day-first, as printed on Indian receipts
		self.assertEqual(parse_date("12/03/2026"), date(2026, 3, 12))
		self.assertEqual(parse_date("12-03-26"), date(2026, 3, 12))
		self.assertEqual(parse_date("12.03.2026"), date(2026, 3, 12))

	def test_month_names(self):
		self.assertEqual(parse_date("12 Mar 2026"), date(2026, 3, 12))
		self.assertEqual(parse_date("12 March 2026"), date(2026, 3, 12))
		self.assertEqual(parse_date("Mar 12, 2026"), date(2026, 3, 12))
		self.assertEqual(parse_date("March 12,2026"), date(2026, 3, 12))

	def test_unreadable(self):
		self.assertIsNone(parse_date("yesterday"))
		self.assertIsNone(parse_date(""))
		self.assertIsNone(parse_date(None))


class TestDetectCurrency(unittest.TestCase):
	def test_codes_and_symbols(self):
		self.assertEqual(detect_currency("inr"), "INR")
		self.assertEqual(detect_currency("₹"), "INR")
		self.assertEqual(detect_currency("Rs."), "INR")
		self.assertEqual(detect_currency("$"), "USD")

	def test_falls_back_to_ocr_text(self):
		self.assertEqual(detect_currency("", "TOTAL ₹ 245.00"), "INR")
		self.assertIsNone(detect_currency("", "TOTAL 245.00"))


def receipt(**overrides):
	data = {
		"vendor": "Annapurna Stores",
		"bill_number": "B-1042",
		"bill_date": "12/03/2026",
		"currency": "INR",
		"line_items": [
			{"description": "Rice 5kg", "quantity": 1, "rate": 320, "amount": 320},
			{"description": "Dal", "quantity": 2, "rate": "80.00", "amount": "160.00"},
		],
		"tax_amount": 24,
		"total_amount": "504.00",
	}
	data.update(overrides)
	return data


class TestParseLLMOutput(unittest.TestCase):
	def test_clean_receipt(self):
		result = parse_llm_output(json.dumps(receipt()))

		self.assertEqual(result.vendor, "Annapurna Stores")
		self.assertEqual(result.bill_date, date(2026, 3, 12))
		self.assertEqual(result.currency, "INR")
		self.assertEqual([line.amount for line in result.lines], [320.0, 160.0])
		self.assertEqual(result.lines_total, 480.0)
		self.assertEqual(result.total_amount, 504.0)
		self.assertEqual(result.warnings, [])

	def test_fills_missing_amount_or_rate(self):
		result = parse_llm_output(
			receipt(
				line_items=[
					{"description": "Soap", "quantity": 3, "rate": 40},  # no amount
					{"description": "Oil", "quantity": 2, "amount": 300},  # no rate
				],
				tax_amount=0,
				total_amount=420,
			)
		)

		self.assertEqual([(line.rate, line.amount) for line in result.lines], [(40.0, 120.0), (150.0, 300.0)])

	def test_skips_unusable_lines(self):
		result = parse_llm_output(
			receipt(
				line_items=[
					{"description": "", "amount": 10},
					{"description": "Tea"},
					"junk",
					{"description": "Milk", "amount": 30},
				],
				total_amount=30,
				tax_amount=0,
			)
		)

		self.assertEqual([line.description for line in result.lines], ["Milk"])

	def test_computes_missing_total_with_warning(self):
		result = parse_llm_output(receipt(total_amount=None))

		self.assertEqual(result.total_amount, 504.0)
		self.assertIn("computed from line items", result.warnings[0])

	def test_flags_totals_that_dont_add_up(self):
		result = parse_llm_output(receipt(total_amount=900))

		self.assertEqual(len(result.warnings), 1)
		self.assertIn("do not match", result.warnings[0])

	def test_tolerates_rounding(self):
		result = parse_llm_output(receipt(total_amount=504.75))

		self.assertEqual(result.warnings, [])

	def test_flags_future_dates_and_unreadable_dates(self):
		future = (date.today() + timedelta(days=30)).isoformat()
		self.assertIn("future", parse_llm_output(receipt(bill_date=future)).warnings[0])
		self.assertIn("Could not read bill date", parse_llm_output(receipt(bill_date="someday")).warnings[0])

	def test_flags_missing_vendor(self):
		self.assertIn("Vendor name not found", parse_llm_output(receipt(vendor="")).warnings)

	def test_rejects_unusable_output(self):
		with self.assertRaises(ExtractionError):
			parse_llm_output("not json")
		with self.assertRaises(ExtractionError):
			parse_llm_output("[1, 2]")
		with self.assertRaises(ExtractionError):
			parse_llm_output(receipt(line_items=[], total_amount=None))
		with self.assertRaises(ExtractionError):
			parse_llm_output(receipt(line_items=[], total_amount=0))


class TestLLMMistakeCorrection(unittest.TestCase):
	"""Mistakes observed from small local models on real runs."""

	OCR = "ANNAPURNA STORES\nDATE 12/03/2026\nRICE 5KG 320.00\nDAL 160.00\nGST 24.00\nTOTAL 504.00"

	def test_drops_total_lines_and_moves_tax_lines_into_tax(self):
		result = parse_llm_output(
			receipt(
				line_items=[
					{"description": "RICE", "amount": 320},
					{"description": "DAL", "amount": 160},
					{"description": "GST", "amount": 24},
					{"description": "TOTAL", "amount": 504},
				],
				tax_amount=0,
				total_amount=504,
			),
			ocr_text=self.OCR,
		)

		self.assertEqual([line.description for line in result.lines], ["RICE", "DAL"])
		self.assertEqual(result.tax_amount, 24.0)
		self.assertEqual(result.warnings, [])

	def test_recognises_common_summary_and_tax_labels(self):
		lines = [
			{"description": label, "amount": 1}
			for label in (
				"Sub Total",
				"Grand Total",
				"Round Off",
				"Amount Payable",
				"CGST 2.5%",
				"SGST @2.5%",
				"VAT",
			)
		]
		result = parse_llm_output(
			receipt(line_items=[{"description": "Tea", "amount": 10}, *lines], tax_amount=0, total_amount=13)
		)

		self.assertEqual([line.description for line in result.lines], ["Tea"])
		self.assertEqual(result.tax_amount, 3.0)  # CGST + SGST + VAT

	def test_keeps_items_that_merely_contain_tax_words(self):
		result = parse_llm_output(
			receipt(
				line_items=[
					{"description": "Taxi fare", "amount": 120},
					{"description": "Totally Fresh Juice", "amount": 80},
				],
				tax_amount=0,
				total_amount=200,
			)
		)

		self.assertEqual(len(result.lines), 2)

	def test_flags_amounts_not_printed_on_the_receipt(self):
		# The model read "RICE 5KG 320.00" as 500.00
		result = parse_llm_output(
			receipt(
				line_items=[{"description": "RICE", "amount": 500}, {"description": "DAL", "amount": 160}],
				tax_amount=24,
				total_amount=504,
			),
			ocr_text=self.OCR,
		)

		self.assertTrue(
			any("500.00" in w and "not found on the receipt" in w for w in result.warnings), result.warnings
		)

	def test_grounding_accepts_formatted_amounts_on_the_receipt(self):
		result = parse_llm_output(
			receipt(
				line_items=[{"description": "Laptop", "amount": 1234.5}], tax_amount=0, total_amount=1234.5
			),
			ocr_text="LAPTOP  Rs.1,234.50\nTOTAL 1234.50",
		)

		self.assertEqual(result.warnings, [])

	def test_keeps_discount_lines_because_they_change_the_total(self):
		result = parse_llm_output(
			receipt(
				line_items=[
					{"description": "Shoes", "amount": 1000},
					{"description": "Discount 10%", "amount": "(100)"},
				],
				tax_amount=0,
				total_amount=900,
			)
		)

		self.assertEqual([line.amount for line in result.lines], [1000.0, -100.0])
		self.assertEqual(result.warnings, [])
