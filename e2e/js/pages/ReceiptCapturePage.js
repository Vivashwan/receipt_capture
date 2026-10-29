import path from "node:path";
import { fileURLToPath } from "node:url";

import { By, Key, until } from "selenium-webdriver";

import { config } from "../support/config.js";
import { DeskPage } from "./DeskPage.js";

const FIXTURES = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../fixtures");
// Statuses after which the background job has finished
const FINISHED = ["Extracted", "Needs Review", "Failed"];
const ROWS = '.frappe-control[data-fieldname="items"] .grid-body .grid-row';

export class ReceiptCapturePage extends DeskPage {
	async openNew() {
		await this.goto("receipt-capture/new");
		await this.findVisible('button.btn-attach[data-fieldname="receipt_image"]');
	}

	async open(name) {
		await this.goto(`receipt-capture/${encodeURIComponent(name)}`);
		await this.driver.wait(
			() => this.driver.executeScript("return !!(window.cur_frm && cur_frm.doc.name === arguments[0])", name),
			20000,
			`Receipt ${name} did not open`,
		);
	}

	async name() {
		return this.docValue("name");
	}

	/** Uploads a fixture through the standard file uploader dialog. */
	async attachReceipt(fixture) {
		await this.click('button.btn-attach[data-fieldname="receipt_image"]');
		// The uploader's <input type=file> is hidden; ChromeDriver still accepts a path for it
		await this.findVisible(".modal.show");
		const input = await this.find(".modal.show input[type=file]");
		await input.sendKeys(path.join(FIXTURES, fixture));
		await this.click(".modal.show .btn-modal-primary");
		await this.driver.wait(async () => !(await this.isPresent(".modal.show")), 30000, "Upload dialog did not close");
		await this.find('.frappe-control[data-fieldname="receipt_image"] a.attached-file-link[href*="/files/"]');
	}

	/** Attaches and saves a new receipt; returns its name (e.g. RCPT-2026-00001). */
	async upload(fixture) {
		await this.openNew();
		await this.attachReceipt(fixture);
		await this.save();
		await this.driver.wait(until.urlMatches(/\/receipt-capture\/(?!new)[^/]+$/), 30000, "Receipt was not saved");
		return this.name();
	}

	/**
	 * Waits for the background job to finish. The page is not reloaded here: the form must
	 * update itself from the realtime event the worker publishes.
	 */
	async waitForExtraction(timeout = config.extractionTimeoutMs) {
		await this.driver.wait(async () => FINISHED.includes(await this.status()), timeout, "Extraction did not finish");
		await this.waitUntilIdle();
		return this.status();
	}

	/** Message set with frm.dashboard.set_headline_alert, shown above the form. */
	async headline() {
		const message = await this.visible(".form-message-container .form-message");
		return message ? message.getText() : "";
	}

	// ---- line items grid ----

	rowCss(idx) {
		return `${ROWS}[data-idx="${idx}"]`;
	}

	async rowCount() {
		return (await this.driver.findElements(By.css(ROWS))).length;
	}

	/** Line items from the form model (a row being edited shows inputs, not text). */
	async lineItems() {
		return (await this.docValue("items")).map(({ description, qty, rate, amount }) => ({ description, qty, rate, amount }));
	}

	/** Adds an empty line and returns its row number. */
	async addRow() {
		const idx = (await this.rowCount()) + 1;
		await this.click('.frappe-control[data-fieldname="items"] .grid-add-row');
		await this.find(this.rowCss(idx));
		return idx;
	}

	/** Types into a grid cell the way a user does: click the cell, type, tab out. */
	async setCell(idx, fieldname, value) {
		const input = `${this.rowCss(idx)} input[data-fieldname="${fieldname}"]`;
		// A new row opens in edit mode; an existing one needs a click on the cell first
		if (!(await this.isPresent(input))) await this.click(`${this.rowCss(idx)} .grid-static-col[data-fieldname="${fieldname}"]`);
		await this.typeInto(input, value);
	}

	async setField(fieldname, value) {
		await this.typeInto(`.frappe-control[data-fieldname="${fieldname}"] input`, value);
	}

	async typeInto(css, value) {
		await this.driver.wait(
			async () => {
				const input = await this.visible(css);
				if (!input) return false;
				try {
					await input.sendKeys(Key.chord(Key.CONTROL, "a"), String(value), Key.TAB);
					return true;
				} catch (error) {
					if (error.name === "StaleElementReferenceError") return false;
					throw error;
				}
			},
			20000,
			`Could not type into ${css}`,
		);
		await this.waitUntilIdle();
	}

	// ---- actions ----

	async createPurchaseInvoice() {
		await this.clickButton("Create Purchase Invoice");
		await this.driver.wait(until.urlMatches(/\/purchase-invoice\/[^/]+$/), 60000, "Did not open the new Purchase Invoice");
		await this.waitUntilIdle();
	}
}
