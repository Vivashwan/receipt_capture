import assert from "node:assert/strict";

import { config } from "../support/config.js";
import { useBrowser } from "../support/session.js";
import { ReceiptCapturePage } from "../pages/ReceiptCapturePage.js";

describe("Unreadable receipt", function () {
	useBrowser({ user: config.reviewer, password: config.userPassword });

	it("fails with a reason the user can act on", async function () {
		const receipt = new ReceiptCapturePage(this.driver);
		await receipt.upload("blank.png");

		assert.equal(await receipt.waitForExtraction(), "Failed");
		assert.match(await receipt.headline(), /No readable text/);
		assert.equal(await receipt.hasButton("Re-run Extraction"), true);
		assert.equal(await receipt.hasButton("Create Purchase Invoice"), false);
	});

	it("lets the user key in lines by hand, with totals kept in sync", async function () {
		const receipt = new ReceiptCapturePage(this.driver);

		const first = await receipt.addRow();
		await receipt.setCell(first, "description", "Printer paper");
		await receipt.setCell(first, "qty", 2);
		await receipt.setCell(first, "rate", 150);
		const second = await receipt.addRow();
		await receipt.setCell(second, "description", "Courier");
		await receipt.setCell(second, "rate", 60);

		assert.equal(await receipt.docValue("lines_total"), 360);
		assert.deepEqual(
			(await receipt.lineItems()).map((line) => line.description),
			["Printer paper", "Courier"],
		);
	});

	it("warns when items and tax don't add up to the total", async function () {
		const receipt = new ReceiptCapturePage(this.driver);

		await receipt.setField("tax_amount", 18);
		await receipt.setField("total_amount", 500);

		await receipt.waitForAlert("don't match the total");
	});

	it("saves the manual corrections", async function () {
		const receipt = new ReceiptCapturePage(this.driver);
		await receipt.setField("total_amount", 378);
		await receipt.save();

		await receipt.open(await receipt.name());
		assert.equal(await receipt.docValue("lines_total"), 360);
		assert.equal(await receipt.docValue("total_amount"), 378);
		assert.equal(await receipt.rowCount(), 2);
	});
});
