import assert from "node:assert/strict";

import { config } from "../support/config.js";
import { useBrowser } from "../support/session.js";
import { DeskPage } from "../pages/DeskPage.js";
import { ReceiptAISettingsPage, TEST_CONNECTION } from "../pages/ReceiptAISettingsPage.js";

describe("Permissions", function () {
	describe("an Accounts User", function () {
		useBrowser({ user: config.reviewer, password: config.userPassword });

		it("can read the AI settings but not test the connection", async function () {
			const settings = new ReceiptAISettingsPage(this.driver);
			await settings.open();

			assert.ok(await settings.docValue("model"));
			assert.equal(await settings.hasButton(TEST_CONNECTION), false);
		});
	});

	describe("a user without an accounts role", function () {
		useBrowser({ user: config.noAccessUser, password: config.userPassword });

		it("is not shown the receipt list", async function () {
			const page = new DeskPage(this.driver);
			await page.goto("receipt-capture");

			const dialog = await page.dialog();
			assert.equal(dialog.title, "Not permitted");
			assert.equal(await page.isPresent(".list-row"), false);
		});
	});
});
