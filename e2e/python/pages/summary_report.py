import json
import time
from urllib.parse import urlencode

from selenium.webdriver.common.by import By

import config
from pages.desk import DeskPage

STATE_SCRIPT = """
	const qr = frappe.query_report;
	if (!qr || !qr.data || qr.report_name !== "Receipt Capture Summary" || frappe.request.ajax_count) return null;
	const applied = qr.get_filter_values();
	const wanted = arguments[0];
	if (Object.keys(wanted).some((key) => String(applied[key]) !== String(wanted[key]))) return null;
	return JSON.stringify(qr.data);
"""


class SummaryReportPage(DeskPage):
	def open(self, filters: dict | None = None):
		"""Opens the report with filters passed as route options in the URL."""
		filters = filters or {}
		self.driver.get(f"{config.BASE_URL}/app/query-report/Receipt Capture Summary?{urlencode(filters)}")
		# The report may run more than once while it applies saved and URL filters, so wait
		# until the filters match, nothing is loading, and the result has stopped changing.
		last = {"state": None, "since": 0.0}

		def stable(driver):
			state = driver.execute_script(STATE_SCRIPT, filters)
			if state is None or state != last["state"]:
				last.update(state=state, since=time.monotonic())
				return False
			return time.monotonic() - last["since"] >= 1

		self.wait(30).until(stable, f"Report did not load with filters {json.dumps(filters)}")

	def rows(self) -> list[dict]:
		"""Rows as returned by the report, read from the page's report object."""
		return self.driver.execute_script("return frappe.query_report.data")

	def summary_cards(self) -> dict:
		cards = {}
		for card in self.driver.find_elements(By.CSS_SELECTOR, ".report-summary .summary-item"):
			label = card.find_element(By.CSS_SELECTOR, ".summary-label").text
			cards[label] = card.find_element(By.CSS_SELECTOR, ".summary-value").text
		return cards
