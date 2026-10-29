import assert from "node:assert/strict";

import { config } from "../support/config.js";
import { useBrowser } from "../support/session.js";
import { ReceiptAISettingsPage } from "../pages/ReceiptAISettingsPage.js";

describe("Receipt AI Settings @smoke", function () {
	useBrowser({ user: config.adminUser, password: config.adminPassword });

	it("reports that the local model is reachable", async function () {
		const settings = new ReceiptAISettingsPage(this.driver);
		await settings.open();
		const model = await settings.docValue("model");

		const dialog = await settings.testConnection();

		assert.equal(dialog.title, "Connected");
		assert.ok(dialog.body.includes(model), `expected "${dialog.body}" to name the model ${model}`);
		await settings.closeDialog();
	});
});
