from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC

import config
from pages.desk import DeskPage

# Statuses after which the background job has finished
FINISHED = ("Extracted", "Needs Review", "Failed")
ROWS = '.frappe-control[data-fieldname="items"] .grid-body .grid-row'


class ReceiptCapturePage(DeskPage):
	def open_new(self):
		self.goto("receipt-capture/new")
		self.find_visible('button.btn-attach[data-fieldname="receipt_image"]')

	def open(self, name: str):
		self.goto(f"receipt-capture/{name}")
		self.wait().until(
			lambda d: d.execute_script(
				"return !!(window.cur_frm && cur_frm.doc.name === arguments[0])", name
			),
			f"Receipt {name} did not open",
		)

	def name(self) -> str:
		return self.doc_value("name")

	def attach_receipt(self, fixture: str):
		"""Uploads a fixture through the standard file uploader dialog."""
		self.click('button.btn-attach[data-fieldname="receipt_image"]')
		# The uploader's <input type=file> is hidden; ChromeDriver still accepts a path for it
		self.find_visible(".modal.show")
		self.find(".modal.show input[type=file]").send_keys(str(config.FIXTURES / fixture))
		self.click(".modal.show .btn-modal-primary")
		self.wait(30).until(lambda _: not self.is_present(".modal.show"), "Upload dialog did not close")
		self.find('.frappe-control[data-fieldname="receipt_image"] a.attached-file-link[href*="/files/"]')

	def upload(self, fixture: str) -> str:
		"""Attaches and saves a new receipt; returns its name (e.g. RCPT-2026-00001)."""
		self.open_new()
		self.attach_receipt(fixture)
		self.save()
		self.wait(30).until(EC.url_matches(r"/receipt-capture/(?!new)[^/]+$"), "Receipt was not saved")
		return self.name()

	def wait_for_extraction(self, timeout=config.EXTRACTION_TIMEOUT) -> str:
		"""
		Waits for the background job to finish. The page is not reloaded here: the form must
		update itself from the realtime event the worker publishes.
		"""
		self.wait(timeout).until(lambda _: self.status() in FINISHED, "Extraction did not finish")
		self.wait_until_idle()
		return self.status()

	def headline(self) -> str:
		"""Message set with frm.dashboard.set_headline_alert, shown above the form."""
		message = self.visible(".form-message-container .form-message")
		return message.text if message else ""

	# ---- line items grid ----

	def row_css(self, idx: int) -> str:
		return f'{ROWS}[data-idx="{idx}"]'

	def row_count(self) -> int:
		return len(self.driver.find_elements(By.CSS_SELECTOR, ROWS))

	def line_items(self) -> list[dict]:
		"""Line items from the form model (a row being edited shows inputs, not text)."""
		keys = ("description", "qty", "rate", "amount")
		return [{key: row.get(key) for key in keys} for row in self.doc_value("items")]

	def add_row(self) -> int:
		"""Adds an empty line and returns its row number."""
		idx = self.row_count() + 1
		self.click('.frappe-control[data-fieldname="items"] .grid-add-row')
		self.find(self.row_css(idx))
		return idx

	def set_cell(self, idx: int, fieldname: str, value):
		"""Types into a grid cell the way a user does: click the cell, type, tab out."""
		input_css = f'{self.row_css(idx)} input[data-fieldname="{fieldname}"]'
		# A new row opens in edit mode; an existing one needs a click on the cell first
		if not self.is_present(input_css):
			self.click(f'{self.row_css(idx)} .grid-static-col[data-fieldname="{fieldname}"]')
		self.type_into(input_css, value)

	def set_field(self, fieldname: str, value):
		self.type_into(f'.frappe-control[data-fieldname="{fieldname}"] input', value)

	def type_into(self, css: str, value):
		def typed(_):
			element = self.visible(css)
			if not element:
				return False
			try:
				element.send_keys(Keys.CONTROL, "a")
				element.send_keys(str(value), Keys.TAB)
				return True
			except StaleElementReferenceException:
				return False

		self.wait().until(typed, f"Could not type into {css}")
		self.wait_until_idle()

	# ---- actions ----

	def create_purchase_invoice(self):
		self.click_button("Create Purchase Invoice")
		self.wait(60).until(
			EC.url_matches(r"/purchase-invoice/[^/]+$"), "Did not open the new Purchase Invoice"
		)
		self.wait_until_idle()
