"""Maintenance commands, available through bench once the app is installed:

bench --site <site> receipt-ai health
bench --site <site> receipt-ai reprocess --status Failed --limit 50
bench --site <site> receipt-ai stats
"""

import click
from frappe.commands import get_site, pass_context


@click.group("receipt-ai")
def receipt_ai():
	"""Receipt Capture maintenance."""


@receipt_ai.command("health")
@pass_context
def health(context):
	"""Check Tesseract and the Ollama model are available."""
	import frappe
	import pytesseract

	from receipt_capture.ai.pipeline import get_client

	frappe.init(site=get_site(context))
	frappe.connect()
	try:
		failed = False
		try:
			click.secho(f"Tesseract {pytesseract.get_tesseract_version()}: ok", fg="green")
		except pytesseract.TesseractNotFoundError:
			click.secho("Tesseract: NOT INSTALLED (apt install tesseract-ocr)", fg="red")
			failed = True

		client = get_client()
		result = client.health()
		if result["ok"]:
			click.secho(f"Ollama {client.base_url} model {client.model}: ok", fg="green")
		else:
			click.secho(f"Ollama: {result['error']}", fg="red")
			failed = True
	finally:
		frappe.destroy()

	if failed:
		raise SystemExit(1)


@receipt_ai.command("reprocess")
@click.option(
	"--status", default="Failed", show_default=True, type=click.Choice(["Failed", "Needs Review", "Pending"])
)
@click.option("--limit", default=50, show_default=True, help="Maximum receipts to queue")
@click.option("--now", is_flag=True, help="Process synchronously in this process instead of queueing")
@pass_context
def reprocess(context, status, limit, now):
	"""Re-run extraction for receipts in a given status (e.g. after fixing Ollama)."""
	import frappe

	from receipt_capture.ai.pipeline import process_receipt

	frappe.init(site=get_site(context))
	frappe.connect()
	try:
		names = frappe.get_all(
			"Receipt Capture", filters={"status": status}, pluck="name", limit=limit, order_by="creation asc"
		)
		for name in names:
			if now:
				process_receipt(name)
				click.echo(f"{name}: {frappe.db.get_value('Receipt Capture', name, 'status')}")
			else:
				frappe.get_doc("Receipt Capture", name).queue_extraction()
		frappe.db.commit()
		click.secho(
			f"{'Processed' if now else 'Queued'} {len(names)} receipt(s) with status {status}", fg="green"
		)
	finally:
		frappe.destroy()


@receipt_ai.command("stats")
@pass_context
def stats(context):
	"""Show receipt counts by status and the average extraction time."""
	import frappe

	frappe.init(site=get_site(context))
	frappe.connect()
	try:
		rows = frappe.get_all(
			"Receipt Capture",
			fields=["status", "count(name) as receipts", "avg(processing_time) as avg_seconds"],
			group_by="status",
			order_by="status",
		)
		if not rows:
			click.echo("No receipts yet")
		for row in rows:
			click.echo(f"{row.status:<14} {row.receipts:>6}   avg {float(row.avg_seconds or 0):6.1f}s")
	finally:
		frappe.destroy()


commands = [receipt_ai]
