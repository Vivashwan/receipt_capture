import { By } from "selenium-webdriver";

import { config } from "../support/config.js";
import { DeskPage } from "./DeskPage.js";

export class SummaryReportPage extends DeskPage {
	/** Opens the report with filters passed as route options in the URL. */
	async open(filters = {}) {
		const query = new URLSearchParams(filters).toString();
		await this.driver.get(`${config.baseUrl}/app/query-report/Receipt Capture Summary?${query}`);
		// The report may run more than once while it applies saved and URL filters, so wait
		// until the filters match, nothing is loading, and the result has stopped changing.
		let previous;
		let stableSince = 0;
		await this.driver.wait(
			async () => {
				const state = await this.driver.executeScript(
					`const qr = frappe.query_report;
					if (!qr || !qr.data || qr.report_name !== "Receipt Capture Summary" || frappe.request.ajax_count) return null;
					const applied = qr.get_filter_values();
					const wanted = arguments[0];
					if (Object.keys(wanted).some((key) => String(applied[key]) !== String(wanted[key]))) return null;
					return JSON.stringify(qr.data);`,
					filters,
				);
				if (state === null || state !== previous) {
					previous = state;
					stableSince = Date.now();
					return false;
				}
				return Date.now() - stableSince >= 1000;
			},
			30000,
			`Report did not load with filters ${JSON.stringify(filters)}`,
		);
	}

	/** Rows as returned by the report, read from the page's report object. */
	async rows() {
		return this.driver.executeScript("return frappe.query_report.data");
	}

	async summaryCards() {
		const cards = {};
		for (const card of await this.driver.findElements(By.css(".report-summary .summary-item"))) {
			const label = await card.findElement(By.css(".summary-label")).getText();
			cards[label] = await card.findElement(By.css(".summary-value")).getText();
		}
		return cards;
	}
}
