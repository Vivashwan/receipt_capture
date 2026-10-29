from pages.desk import DeskPage

TEST_CONNECTION = "Test Ollama Connection"


class ReceiptAISettingsPage(DeskPage):
	def open(self):
		self.goto("receipt-ai-settings")
		self.find_visible('.frappe-control[data-fieldname="ollama_url"]')

	def test_connection(self) -> dict:
		"""Clicks "Test Ollama Connection" and returns the resulting dialog."""
		self.click_button(TEST_CONNECTION)
		# First call may load the model into memory
		return self.dialog(120)
