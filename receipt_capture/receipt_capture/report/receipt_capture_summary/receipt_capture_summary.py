# Copyright (c) 2026, Vivashwan Ghosh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder.functions import Avg, Count, Sum
from frappe.utils import flt
from pypika.terms import Case


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data), get_summary(data)


def get_columns():
	return [
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 180,
		},
		{"label": _("Vendor (as printed)"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 180},
		{"label": _("Receipts"), "fieldname": "receipts", "fieldtype": "Int", "width": 90},
		{"label": _("Invoiced"), "fieldname": "invoiced", "fieldtype": "Int", "width": 90},
		{"label": _("Needs Attention"), "fieldname": "needs_attention", "fieldtype": "Int", "width": 120},
		{"label": _("Total Amount"), "fieldname": "total_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Pending Amount"), "fieldname": "pending_amount", "fieldtype": "Currency", "width": 130},
		{
			"label": _("Avg Extraction (s)"),
			"fieldname": "avg_processing_time",
			"fieldtype": "Float",
			"precision": 1,
			"width": 130,
		},
	]


def get_data(filters):
	"""One row per supplier, aggregated in a single SQL query."""
	rc = frappe.qb.DocType("Receipt Capture")
	is_invoiced = rc.status == "Invoiced"
	needs_attention = rc.status.isin(["Needs Review", "Failed"])

	query = (
		frappe.qb.from_(rc)
		.select(
			rc.supplier,
			rc.supplier_name,
			Count(rc.name).as_("receipts"),
			Sum(Case().when(is_invoiced, 1).else_(0)).as_("invoiced"),
			Sum(Case().when(needs_attention, 1).else_(0)).as_("needs_attention"),
			Sum(rc.total_amount).as_("total_amount"),
			Sum(Case().when(is_invoiced, 0).else_(rc.total_amount)).as_("pending_amount"),
			Avg(rc.processing_time).as_("avg_processing_time"),
		)
		.where(rc.status != "Pending")
		.groupby(rc.supplier, rc.supplier_name)
		.orderby(Sum(rc.total_amount), order=frappe.qb.desc)
	)

	if filters.company:
		query = query.where(rc.company == filters.company)
	if filters.from_date:
		query = query.where(rc.bill_date >= filters.from_date)
	if filters.to_date:
		query = query.where(rc.bill_date <= filters.to_date)
	if filters.status:
		query = query.where(rc.status == filters.status)

	return query.run(as_dict=True)


def get_chart(data):
	top = data[:10]
	if not top:
		return None
	return {
		"data": {
			"labels": [row.supplier or row.supplier_name or _("Unknown") for row in top],
			"datasets": [
				{
					"name": _("Invoiced"),
					"values": [flt(row.total_amount) - flt(row.pending_amount) for row in top],
				},
				{"name": _("Pending"), "values": [flt(row.pending_amount) for row in top]},
			],
		},
		"type": "bar",
		"barOptions": {"stacked": 1},
		"fieldtype": "Currency",
	}


def get_summary(data):
	receipts = sum(row.receipts for row in data)
	attention = sum(flt(row.needs_attention) for row in data)
	return [
		{"label": _("Receipts"), "value": receipts, "datatype": "Int", "indicator": "Blue"},
		{
			"label": _("Total Amount"),
			"value": sum(flt(r.total_amount) for r in data),
			"datatype": "Currency",
			"indicator": "Green",
		},
		{
			"label": _("Pending Amount"),
			"value": sum(flt(r.pending_amount) for r in data),
			"datatype": "Currency",
			"indicator": "Orange",
		},
		{
			"label": _("Needs Attention"),
			"value": attention,
			"datatype": "Int",
			"indicator": "Red" if attention else "Green",
		},
	]
