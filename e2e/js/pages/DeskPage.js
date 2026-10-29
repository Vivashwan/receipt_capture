import { By, Key, until } from "selenium-webdriver";

import { config } from "../support/config.js";

const DEFAULT_TIMEOUT = 20000;

/** Shared helpers for any page inside the Frappe desk (/app/...). */
export class DeskPage {
	constructor(driver) {
		this.driver = driver;
	}

	async goto(route) {
		await this.driver.get(`${config.baseUrl}/app/${route}`);
		await this.waitUntilIdle();
	}

	/** Frappe renders asynchronously: wait until the page is loaded, no request is running and nothing is frozen. */
	async waitUntilIdle(timeout = DEFAULT_TIMEOUT) {
		await this.driver.wait(
			() =>
				this.driver.executeScript(
					`return document.readyState === "complete"
						&& !!window.frappe && !!frappe.boot
						&& !(frappe.request && frappe.request.ajax_count)
						&& !document.querySelector("#freeze.in")`,
				),
			timeout,
			"Desk did not become idle",
		);
	}

	async find(css, timeout = DEFAULT_TIMEOUT) {
		return this.driver.wait(until.elementLocated(By.css(css)), timeout, `No element matches ${css}`);
	}

	/**
	 * First visible match. Frappe keeps previously visited pages in the DOM (hidden), so the
	 * first match in document order can belong to a page that is no longer on screen.
	 */
	async findVisible(css, timeout = DEFAULT_TIMEOUT) {
		return this.driver.wait(() => this.visible(css), timeout, `${css} is not visible`);
	}

	async visible(css) {
		for (const element of await this.driver.findElements(By.css(css))) {
			try {
				if (await element.isDisplayed()) return element;
			} catch (error) {
				// Re-rendered while we looked at it; the next poll finds the new element
				if (error.name !== "StaleElementReferenceError") throw error;
			}
		}
		return null;
	}

	async isPresent(css) {
		return (await this.visible(css)) !== null;
	}

	/** Clicks the visible element, retrying if Frappe re-renders it between finding and clicking. */
	async click(css, timeout = DEFAULT_TIMEOUT) {
		await this.driver.wait(
			async () => {
				const element = await this.visible(css);
				if (!element || !(await element.isEnabled())) return false;
				try {
					await element.click();
					return true;
				} catch (error) {
					if (["StaleElementReferenceError", "ElementClickInterceptedError"].includes(error.name)) return false;
					throw error;
				}
			},
			timeout,
			`Could not click ${css}`,
		);
	}

	/** Status pill in the page header, e.g. "Draft" or "Extracted". */
	async status() {
		return (await this.findVisible(".page-head .indicator-pill")).getText();
	}

	async title() {
		return (await this.findVisible(".page-head .title-text")).getText();
	}

	// ---- form buttons added with frm.add_custom_button ----

	buttonCss(label) {
		return `.page-head button[data-label="${encodeURIComponent(label)}"]`;
	}

	async hasButton(label) {
		return this.isPresent(this.buttonCss(label));
	}

	async clickButton(label) {
		await this.click(this.buttonCss(label));
	}

	async save() {
		await this.driver.findElement(By.css("body")).sendKeys(Key.chord(Key.CONTROL, "s"));
		await this.waitUntilIdle();
	}

	// ---- dialogs and toasts ----

	async dialog(timeout = DEFAULT_TIMEOUT) {
		const modal = await this.findVisible(".modal.show", timeout);
		return {
			title: await modal.findElement(By.css(".modal-title")).getText(),
			body: await modal.findElement(By.css(".modal-body")).getText(),
		};
	}

	async closeDialog() {
		// Escape closes the top-most Frappe dialog, even while its open animation is running
		await this.driver.wait(
			async () => {
				if (!(await this.isPresent(".modal.show"))) return true;
				await this.driver.findElement(By.css("body")).sendKeys(Key.ESCAPE);
				return false;
			},
			DEFAULT_TIMEOUT,
			"Dialog did not close",
		);
	}

	async waitForAlert(text, timeout = DEFAULT_TIMEOUT) {
		const xpath = `//*[@id="alert-container"]//*[contains(@class,"alert")][contains(., ${JSON.stringify(text)})]`;
		return this.driver.wait(until.elementLocated(By.xpath(xpath)), timeout, `No alert containing "${text}"`);
	}

	// ---- field values ----

	/** Displayed value of a field, whether it renders as an input or as read-only text. */
	async fieldText(fieldname) {
		const control = await this.findVisible(`.frappe-control[data-fieldname="${fieldname}"]`);
		const readOnly = await control.findElements(By.css(".control-value"));
		if (readOnly.length && (await readOnly[0].isDisplayed())) return readOnly[0].getText();
		return control.findElement(By.css("input, textarea, select")).getAttribute("value");
	}

	/**
	 * The document shown by the current route (/app/<doctype>/<name>), read from Frappe's
	 * client-side model, including unsaved edits. Avoids parsing formatted text such as
	 * "₹ 504.00", and unlike the cur_frm global it can't point at the previous form right
	 * after a route change.
	 */
	async doc(timeout = DEFAULT_TIMEOUT) {
		const script = `
			const [view, doctype, name = doctype] = frappe.get_route(); // single doctypes have no name in the route
			const doc = view === "Form" && locals[doctype] && locals[doctype][name];
			return doc && !doc.__islocal ? JSON.parse(JSON.stringify(doc)) : null;`;
		return this.driver.wait(() => this.driver.executeScript(script), timeout, "No saved document is open");
	}

	async docValue(fieldname) {
		return (await this.doc())[fieldname];
	}
}
