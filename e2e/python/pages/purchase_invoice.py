from pages.desk import DeskPage


class PurchaseInvoicePage(DeskPage):
	def details(self) -> dict:
		doc = self.doc()
		assert doc["doctype"] == "Purchase Invoice", f"Expected a Purchase Invoice, got {doc['doctype']}"
		return {
			"name": doc["name"],
			"docstatus": doc["docstatus"],
			"supplier": doc.get("supplier"),
			"bill_no": doc.get("bill_no"),
			"grand_total": doc["grand_total"],
			"total_taxes": doc["total_taxes_and_charges"],
			"items": [
				{
					"item_code": item["item_code"],
					"description": item.get("description"),
					"amount": item["amount"],
				}
				for item in doc["items"]
			],
		}
