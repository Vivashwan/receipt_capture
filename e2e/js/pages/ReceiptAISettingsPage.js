import { DeskPage } from "./DeskPage.js";

export const TEST_CONNECTION = "Test Ollama Connection";

export class ReceiptAISettingsPage extends DeskPage {
	async open() {
		await this.goto("receipt-ai-settings");
		await this.findVisible('.frappe-control[data-fieldname="ollama_url"]');
	}

	/** Clicks "Test Ollama Connection" and returns the resulting dialog. */
	async testConnection() {
		await this.clickButton(TEST_CONNECTION);
		// First call may load the model into memory
		return this.dialog(120000);
	}
}
