import assert from "node:assert/strict";

import { config } from "../support/config.js";
import { useBrowser } from "../support/session.js";
import { LoginPage } from "../pages/LoginPage.js";

describe("Login @smoke", function () {
	useBrowser();

	it("rejects a wrong password and stays on the login page", async function () {
		const login = new LoginPage(this.driver);
		await login.open();
		await login.submit(config.adminUser, "not-the-password");

		assert.match(await login.waitForError(), /Invalid Login/);
		assert.match(await this.driver.getCurrentUrl(), /\/login/);
	});

	it("logs in with valid credentials and opens the desk", async function () {
		await new LoginPage(this.driver).loginAs(config.adminUser, config.adminPassword);

		assert.match(await this.driver.getCurrentUrl(), /\/app/);
	});
});
