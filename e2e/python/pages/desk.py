import json
from urllib.parse import quote

from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config

DEFAULT_TIMEOUT = 20

# Model values for the document shown by the current route (/app/<doctype>/<name>), including
# unsaved edits. Unlike the cur_frm global it can't point at the previous form right after a
# route change, and it avoids parsing formatted text such as "₹ 504.00".
DOC_SCRIPT = """
	const [view, doctype, name = doctype] = frappe.get_route(); // single doctypes have no name in the route
	const doc = view === "Form" && locals[doctype] && locals[doctype][name];
	return doc && !doc.__islocal ? JSON.parse(JSON.stringify(doc)) : null;
"""

IDLE_SCRIPT = """
	return document.readyState === "complete"
		&& !!window.frappe && !!frappe.boot
		&& !(frappe.request && frappe.request.ajax_count)
		&& !document.querySelector("#freeze.in")
"""


class DeskPage:
	"""Shared helpers for any page inside the Frappe desk (/app/...)."""

	def __init__(self, driver):
		self.driver = driver

	def wait(self, timeout=DEFAULT_TIMEOUT) -> WebDriverWait:
		return WebDriverWait(self.driver, timeout)

	def goto(self, route: str):
		self.driver.get(f"{config.BASE_URL}/app/{route}")
		self.wait_until_idle()

	def wait_until_idle(self, timeout=DEFAULT_TIMEOUT):
		"""Frappe renders asynchronously: wait until the page is loaded, no request is running and nothing is frozen."""
		self.wait(timeout).until(lambda d: d.execute_script(IDLE_SCRIPT), "Desk did not become idle")

	def find(self, css: str, timeout=DEFAULT_TIMEOUT) -> WebElement:
		return self.wait(timeout).until(
			EC.presence_of_element_located((By.CSS_SELECTOR, css)), f"No element matches {css}"
		)

	def visible(self, css: str) -> WebElement | None:
		"""
		First visible match. Frappe keeps previously visited pages in the DOM (hidden), so the
		first match in document order can belong to a page that is no longer on screen.
		"""
		for element in self.driver.find_elements(By.CSS_SELECTOR, css):
			try:
				if element.is_displayed():
					return element
			except StaleElementReferenceException:
				pass  # re-rendered while we looked at it; the next poll finds the new element
		return None

	def find_visible(self, css: str, timeout=DEFAULT_TIMEOUT) -> WebElement:
		return self.wait(timeout).until(lambda _: self.visible(css), f"{css} is not visible")

	def is_present(self, css: str) -> bool:
		return self.visible(css) is not None

	def click(self, css: str, timeout=DEFAULT_TIMEOUT):
		"""Clicks the visible element, retrying if Frappe re-renders it between finding and clicking."""

		def clicked(_):
			element = self.visible(css)
			if not element or not element.is_enabled():
				return False
			try:
				element.click()
				return True
			except (StaleElementReferenceException, ElementClickInterceptedException):
				return False

		self.wait(timeout).until(clicked, f"Could not click {css}")

	def status(self) -> str:
		"""Status pill in the page header, e.g. "Draft" or "Extracted"."""
		return self.find_visible(".page-head .indicator-pill").text

	# ---- form buttons added with frm.add_custom_button ----

	def button_css(self, label: str) -> str:
		# Frappe stores the label URI-encoded, like JavaScript's encodeURIComponent
		return f'.page-head button[data-label="{quote(label, safe="!~*()")}"]'

	def has_button(self, label: str) -> bool:
		return self.is_present(self.button_css(label))

	def click_button(self, label: str):
		self.click(self.button_css(label))

	def save(self):
		self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.CONTROL, "s")
		self.wait_until_idle()

	# ---- dialogs and toasts ----

	def dialog(self, timeout=DEFAULT_TIMEOUT) -> dict:
		modal = self.find_visible(".modal.show", timeout)
		return {
			"title": modal.find_element(By.CSS_SELECTOR, ".modal-title").text,
			"body": modal.find_element(By.CSS_SELECTOR, ".modal-body").text,
		}

	def close_dialog(self):
		# Escape closes the top-most Frappe dialog, even while its open animation is running
		def closed(_):
			if not self.is_present(".modal.show"):
				return True
			self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
			return False

		self.wait().until(closed, "Dialog did not close")

	def wait_for_alert(self, text: str, timeout=DEFAULT_TIMEOUT) -> WebElement:
		xpath = f'//*[@id="alert-container"]//*[contains(@class,"alert")][contains(., {json.dumps(text)})]'
		return self.wait(timeout).until(
			EC.presence_of_element_located((By.XPATH, xpath)), f'No alert containing "{text}"'
		)

	# ---- field values ----

	def doc(self, timeout=DEFAULT_TIMEOUT) -> dict:
		return self.wait(timeout).until(lambda d: d.execute_script(DOC_SCRIPT), "No saved document is open")

	def doc_value(self, fieldname: str):
		return self.doc()[fieldname]
