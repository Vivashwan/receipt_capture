import assert from "node:assert/strict";

import { config } from "../support/config.js";
import { useBrowser } from "../support/session.js";
import { SummaryReportPage } from "../pages/SummaryReportPage.js";

const today = new Date().toISOString().slice(0, 10);
const yearStart = `${today.slice(0, 4)}-01-01`;

describe("Receipt Capture Summary report", function () {
	useBrowser({ user: config.reviewer, password: config.userPassword });

	it("aggregates receipts per supplier with invoiced and pending amounts", async function () {
		const report = new SummaryReportPage(this.driver);
		await report.open({ from_date: yearStart, to_date: today });

		const rows = await report.rows();
		const annapurna = rows.find((row) => /annapurna/i.test(row.supplier_name || ""));
		assert.ok(annapurna, `no Annapurna row in ${JSON.stringify(rows)}`);
		assert.ok(annapurna.receipts >= 1);
		assert.ok(annapurna.invoiced >= 1, "the receipt invoiced in the main flow is counted");

		const cards = await report.summaryCards();
		assert.ok(Number(cards.Receipts) >= 1, JSON.stringify(cards));
	});

	it("still shows failed receipts, which have no bill date, inside a date range", async function () {
		const report = new SummaryReportPage(this.driver);
		await report.open({ from_date: today, to_date: today, status: "Failed" });

		const rows = await report.rows();
		assert.ok(rows.reduce((sum, row) => sum + row.receipts, 0) >= 1, JSON.stringify(rows));
		assert.notEqual((await report.summaryCards())["Needs Attention"], "0");
	});
});
