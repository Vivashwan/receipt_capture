import { Builder, logging } from "selenium-webdriver";
import chrome from "selenium-webdriver/chrome.js";

import { config } from "./config.js";

export async function createDriver() {
	const options = new chrome.Options().addArguments("--window-size=1440,1000", "--disable-dev-shm-usage");
	if (config.headless) options.addArguments("--headless=new");
	// Keep the browser console, saved on failure (realtime and JS errors only show up there)
	const prefs = new logging.Preferences();
	prefs.setLevel(logging.Type.BROWSER, logging.Level.ALL);
	options.setLoggingPrefs(prefs);

	const builder = new Builder().forBrowser("chrome").setChromeOptions(options);
	if (config.remoteUrl) builder.usingServer(config.remoteUrl);

	const driver = await builder.build();
	// Explicit waits only: an implicit wait would slow down every "element is absent" check
	await driver.manage().setTimeouts({ implicit: 0, pageLoad: 60000, script: 30000 });
	return driver;
}
