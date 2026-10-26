// Copyright (c) 2026, Vivashwan Ghosh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Receipt AI Settings", {
	setup(frm) {
		frm.set_query("expense_item", () => ({ filters: { is_stock_item: 0, disabled: 0 } }));
		frm.set_query("supplier_group", () => ({ filters: { is_group: 0 } }));
		frm.set_query("tax_account", () => ({ filters: { account_type: "Tax", is_group: 0 } }));
	},

	refresh(frm) {
		frm.add_custom_button(__("Test Ollama Connection"), () => {
			frappe
				.call({ method: "receipt_capture.api.check_ollama", freeze: true, freeze_message: __("Contacting Ollama…") })
				.then(({ message }) => {
					if (message.ok) {
						frappe.msgprint({ title: __("Connected"), message: __("Model {0} is ready.", [frm.doc.model]), indicator: "green" });
					} else {
						frappe.msgprint({ title: __("Not ready"), message: frappe.utils.escape_html(message.error), indicator: "red" });
					}
				});
		});
	},
});
