import { By, until } from "selenium-webdriver";

import { config } from "../support/config.js";

export class LoginPage {
	constructor(driver) {
		this.driver = driver;
	}

	async open() {
		await this.driver.get(`${config.baseUrl}/login`);
		await this.driver.wait(until.elementLocated(By.id("login_email")), 20000);
	}

	async submit(user, password) {
		const email = await this.driver.findElement(By.id("login_email"));
		const secret = await this.driver.findElement(By.id("login_password"));
		await email.clear();
		await email.sendKeys(user);
		await secret.clear();
		await secret.sendKeys(password);
		await this.driver.findElement(By.css(".btn-login")).click();
	}

	/** Logs in and waits for the desk. */
	async loginAs(user, password) {
		await this.open();
		await this.submit(user, password);
		await this.driver.wait(until.urlContains("/app"), 30000, `Login as ${user} did not reach the desk`);
	}

	/** Frappe shows a failed login in the button itself. */
	async waitForError() {
		const button = await this.driver.findElement(By.css(".btn-login"));
		await this.driver.wait(async () => (await button.getText()).includes("Invalid"), 15000, "No login error shown");
		return button.getText();
	}
}

export async function logout(driver) {
	await driver.get(`${config.baseUrl}/api/method/logout`);
	await driver.manage().deleteAllCookies();
}
