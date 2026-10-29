import { createDriver } from "./driver.js";
import { LoginPage } from "../pages/LoginPage.js";

/**
 * Opens one browser per `describe` block, optionally logged in. The driver is put on the
 * Mocha context as `this.driver`, which the failure hook in hooks.js uses for screenshots.
 */
export function useBrowser({ user, password } = {}) {
	before(async function () {
		this.driver = await createDriver();
		if (user) await new LoginPage(this.driver).loginAs(user, password);
	});

	after(async function () {
		await this.driver?.quit();
	});
}
