import { DeskPage } from "./DeskPage.js";

export class PurchaseInvoicePage extends DeskPage {
	async details() {
		const doc = await this.doc();
		if (doc.doctype !== "Purchase Invoice") throw new Error(`Expected a Purchase Invoice, got ${doc.doctype}`);
		return {
			name: doc.name,
			docstatus: doc.docstatus,
			supplier: doc.supplier,
			bill_no: doc.bill_no,
			grand_total: doc.grand_total,
			total_taxes: doc.total_taxes_and_charges,
			items: doc.items.map((item) => ({ item_code: item.item_code, description: item.description, amount: item.amount })),
		};
	}
}
