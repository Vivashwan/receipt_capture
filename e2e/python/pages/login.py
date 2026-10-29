from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config


class LoginPage:
	def __init__(self, driver):
		self.driver = driver

	def open(self):
		self.driver.get(f"{config.BASE_URL}/login")
		WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.ID, "login_email")))

	def submit(self, user: str, password: str):
		for field_id, value in (("login_email", user), ("login_password", password)):
			field = self.driver.find_element(By.ID, field_id)
			field.clear()
			field.send_keys(value)
		self.driver.find_element(By.CSS_SELECTOR, ".btn-login").click()

	def login_as(self, user: str, password: str):
		"""Logs in and waits for the desk."""
		self.open()
		self.submit(user, password)
		WebDriverWait(self.driver, 30).until(
			EC.url_contains("/app"), f"Login as {user} did not reach the desk"
		)

	def wait_for_error(self) -> str:
		"""Frappe shows a failed login in the button itself."""
		button = self.driver.find_element(By.CSS_SELECTOR, ".btn-login")
		WebDriverWait(self.driver, 15).until(lambda _: "Invalid" in button.text, "No login error shown")
		return button.text
