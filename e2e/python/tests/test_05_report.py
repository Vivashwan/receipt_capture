import json
import re
from datetime import date

import config
from conftest import browser_for
from pages.summary_report import SummaryReportPage

browser = browser_for(config.REVIEWER, config.USER_PASSWORD)

TODAY = date.today().isoformat()
YEAR_START = f"{TODAY[:4]}-01-01"


def test_aggregates_receipts_per_supplier_with_invoiced_and_pending_amounts(browser):
	report = SummaryReportPage(browser)
	report.open({"from_date": YEAR_START, "to_date": TODAY})

	rows = report.rows()
	annapurna = next(
		(row for row in rows if re.search("annapurna", row.get("supplier_name") or "", re.I)), None
	)
	assert annapurna, f"no Annapurna row in {json.dumps(rows)}"
	assert annapurna["receipts"] >= 1
	assert annapurna["invoiced"] >= 1, "the receipt invoiced in the main flow is counted"

	cards = report.summary_cards()
	assert int(cards["Receipts"]) >= 1, cards


def test_still_shows_failed_receipts_which_have_no_bill_date_inside_a_date_range(browser):
	report = SummaryReportPage(browser)
	report.open({"from_date": TODAY, "to_date": TODAY, "status": "Failed"})

	rows = report.rows()
	assert sum(row["receipts"] for row in rows) >= 1, rows
	assert report.summary_cards()["Needs Attention"] != "0"
