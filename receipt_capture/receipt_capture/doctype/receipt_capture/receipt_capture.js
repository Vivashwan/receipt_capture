// Copyright (c) 2026, Vivashwan Ghosh and contributors
// For license information, please see license.txt

const STATUS_COLORS = {
	Pending: "gray",
	Processing: "orange",
	Extracted: "green",
	"Needs Review": "yellow",
	Failed: "red",
	Invoiced: "blue",
};

frappe.ui.form.on("Receipt Capture", {
	setup(frm) {
		// Only non-stock items make sense on an expense receipt
		frm.set_query("item_code", "items", () => ({ filters: { is_stock_item: 0, disabled: 0 } }));
		frm.set_query("supplier", () => ({ filters: { disabled: 0 } }));

		// The background job saves the receipt, and Frappe reloads the open form on that
		// doc_update when it has no unsaved changes. Reloading here as well would race
		// Frappe's (debounced) reload, which could then wipe edits made in between. So only
		// tell the user. Registered in setup, which runs once per form, not on every load.
		frappe.realtime.on("receipt_capture_update", (data) => {
			if (data.name === frm.doc.name) {
				frappe.show_alert({
					message: __("Extraction finished: {0}", [__(data.status)]),
					indicator: STATUS_COLORS[data.status] || "blue",
				});
			}
		});
	},

	refresh(frm) {
		frm.page.set_indicator(__(frm.doc.status), STATUS_COLORS[frm.doc.status] || "gray");
		show_alerts(frm);
		if (frm.is_new()) return;

		if (["Pending", "Extracted", "Needs Review", "Failed"].includes(frm.doc.status)) {
			const label = frm.doc.status === "Pending" ? __("Extract with AI") : __("Re-run Extraction");
			frm.add_custom_button(label, () => {
				if (frm.is_dirty()) {
					frappe.msgprint(__("Save your changes first; re-running replaces the extracted fields."));
					return;
				}
				frm.call("extract").then(() => frm.reload_doc());
			});
		}

		if (["Extracted", "Needs Review"].includes(frm.doc.status)) {
			frm.add_custom_button(
				__("Create Purchase Invoice"),
				() => {
					// `doc` makes this a call to the document's method, not a module-level function
					frm.call({ doc: frm.doc, method: "make_purchase_invoice", freeze: true, freeze_message: __("Creating invoice…") }).then((r) => {
						if (r.message) frappe.set_route("Form", "Purchase Invoice", r.message);
					});
				},
				null,
			).addClass("btn-primary");
		}

		if (frm.doc.purchase_invoice) {
			frm.add_custom_button(__("Open Purchase Invoice"), () =>
				frappe.set_route("Form", "Purchase Invoice", frm.doc.purchase_invoice),
			);
		}
	},

	tax_amount: (frm) => frm.trigger("check_totals"),
	total_amount: (frm) => frm.trigger("check_totals"),

	check_totals(frm) {
		const expected = flt(frm.doc.lines_total) + flt(frm.doc.tax_amount);
		if (frm.doc.items?.length && Math.abs(expected - flt(frm.doc.total_amount)) > 1) {
			frappe.show_alert({
				message: __("Items + tax ({0}) don't match the total ({1})", [
					format_currency(expected, frm.doc.currency),
					format_currency(frm.doc.total_amount, frm.doc.currency),
				]),
				indicator: "orange",
			});
		}
	},
});

frappe.ui.form.on("Receipt Capture Item", {
	qty: (frm, cdt, cdn) => update_amount(frm, cdt, cdn),
	rate: (frm, cdt, cdn) => update_amount(frm, cdt, cdn),
	amount: (frm) => update_lines_total(frm),
	items_remove: (frm) => update_lines_total(frm),
});

function update_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", flt(row.qty || 1) * flt(row.rate));
	update_lines_total(frm);
}

function update_lines_total(frm) {
	const total = (frm.doc.items || []).reduce((sum, row) => sum + flt(row.amount), 0);
	frm.set_value("lines_total", total);
	frm.trigger("check_totals");
}

function show_alerts(frm) {
	frm.dashboard.clear_headline();
	if (frm.doc.status === "Processing") {
		frm.dashboard.set_headline_alert(__("Reading the receipt with OCR and the local model… this page updates when done."), "orange");
	} else if (frm.doc.status === "Failed" && frm.doc.error_message) {
		frm.dashboard.set_headline_alert(frappe.utils.escape_html(frm.doc.error_message), "red");
	} else if (frm.doc.status === "Needs Review" && frm.doc.review_notes) {
		frm.dashboard.set_headline_alert(
			__("Please check before invoicing:") + "<br>" + frappe.utils.escape_html(frm.doc.review_notes).replace(/\n/g, "<br>"),
			"yellow",
		);
	}
}
