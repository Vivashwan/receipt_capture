import fs from "node:fs/promises";
import path from "node:path";

import { logging } from "selenium-webdriver";

import { config } from "./config.js";

// Root hooks: on any failure save a screenshot and the page HTML, so CI shows what the browser saw
export const mochaHooks = {
	async afterEach() {
		const driver = this.currentTest?.ctx?.driver;
		if (this.currentTest?.state !== "failed" || !driver) return;

		await fs.mkdir(config.artifactsDir, { recursive: true });
		const name = this.currentTest.fullTitle().replace(/[^a-z0-9]+/gi, "-").slice(0, 120);
		try {
			await fs.writeFile(path.join(config.artifactsDir, `${name}.png`), await driver.takeScreenshot(), "base64");
			await fs.writeFile(path.join(config.artifactsDir, `${name}.html`), await driver.getPageSource());
			const console = await driver.manage().logs().get(logging.Type.BROWSER);
			await fs.writeFile(
				path.join(config.artifactsDir, `${name}.console.log`),
				console.map((entry) => `${entry.level.name} ${entry.message}`).join("\n"),
			);
		} catch (error) {
			console.warn(`Could not capture failure artifacts: ${error.message}`);
		}
	},
};
