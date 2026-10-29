import assert from "node:assert/strict";

import { config } from "../support/config.js";
import { useBrowser } from "../support/session.js";
import { PurchaseInvoicePage } from "../pages/PurchaseInvoicePage.js";
import { ReceiptCapturePage } from "../pages/ReceiptCapturePage.js";

// The fixture is a tilted, noisy photo of: RICE 320.00 / DAL 160.00 / GST 24.00 / TOTAL 504.00

describe("Receipt photo to draft Purchase Invoice", function () {
	useBrowser({ user: config.reviewer, password: config.userPassword });

	let receiptName;

	it("uploads a receipt photo and queues extraction", async function () {
		const receipt = new ReceiptCapturePage(this.driver);
		receiptName = await receipt.upload("receipt.png");

		assert.match(receiptName, /^RCPT-/);
		assert.equal(await receipt.status(), "Processing");
		assert.match(await receipt.headline(), /Reading the receipt/);
	});

	it("updates the open form live when the background job finishes", async function () {
		const receipt = new ReceiptCapturePage(this.driver);

		const status = await receipt.waitForExtraction();

		assert.ok(["Extracted", "Needs Review"].includes(status), `unexpected status ${status}`);
		await receipt.waitForAlert("Extraction finished");
	});

	it("fills vendor, line items, tax and total from the photo", async function () {
		const receipt = new ReceiptCapturePage(this.driver);

		assert.match(await receipt.docValue("supplier_name"), /annapurna/i);
		assert.equal(await receipt.docValue("total_amount"), 504);
		assert.equal(await receipt.docValue("tax_amount"), 24);
		const lines = await receipt.lineItems();
		const descriptions = lines.map((line) => line.description.toUpperCase()).join(" | ");
		assert.match(descriptions, /RICE/);
		assert.match(descriptions, /DAL/);
		assert.ok(!/TOTAL|GST/.test(descriptions), `summary or tax rows leaked into the items: ${descriptions}`);
	});

	it("creates a draft Purchase Invoice with the receipt's amounts", async function () {
		const receipt = new ReceiptCapturePage(this.driver);
		await receipt.createPurchaseInvoice();

		const invoice = new PurchaseInvoicePage(this.driver);
		const details = await invoice.details();

		assert.equal(await invoice.status(), "Draft");
		assert.equal(details.docstatus, 0, "invoices are left as drafts for an accountant to submit");
		assert.equal(details.grand_total, 504);
		assert.equal(details.total_taxes, 24);
		assert.ok(details.supplier, "a supplier is matched or created");
		assert.ok(details.items.every((item) => item.item_code === "Receipt Expense"));
	});

	it("marks the receipt Invoiced and locks it", async function () {
		const receipt = new ReceiptCapturePage(this.driver);
		await receipt.open(receiptName);

		assert.equal(await receipt.status(), "Invoiced");
		assert.ok(await receipt.docValue("purchase_invoice"));
		assert.equal(await receipt.hasButton("Open Purchase Invoice"), true);
		assert.equal(await receipt.hasButton("Create Purchase Invoice"), false, "can't invoice twice");
		assert.equal(await receipt.hasButton("Re-run Extraction"), false, "can't overwrite an invoiced receipt");
	});
});
