import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from receipt_capture.ai.extraction import RECEIPT_SCHEMA
from receipt_capture.ai.llm import LLMError, OllamaClient


def ollama_response(status=200, content=None, payload=None):
	response = MagicMock(status_code=status, ok=200 <= status < 300, text="error body")
	response.json.return_value = payload if payload is not None else {"message": {"content": content}}
	return response


class TestOllamaClient(unittest.TestCase):
	def setUp(self):
		self.client = OllamaClient("http://ollama:11434/", "qwen2.5:1.5b", timeout=30)

	@patch("receipt_capture.ai.llm.requests.post")
	def test_sends_schema_constrained_deterministic_request(self, post):
		post.return_value = ollama_response(content=json.dumps({"vendor": "A", "total_amount": 10}))

		result = self.client.extract_receipt("RECEIPT TEXT")

		self.assertEqual(result, {"vendor": "A", "total_amount": 10})
		url = post.call_args.args[0]
		body = post.call_args.kwargs["json"]
		self.assertEqual(url, "http://ollama:11434/api/chat")  # trailing slash normalised
		self.assertEqual(body["model"], "qwen2.5:1.5b")
		self.assertEqual(body["format"], RECEIPT_SCHEMA)
		self.assertEqual(body["options"]["temperature"], 0)
		self.assertFalse(body["stream"])
		self.assertIn("RECEIPT TEXT", body["messages"][-1]["content"])
		self.assertEqual(post.call_args.kwargs["timeout"], 30)

	@patch("receipt_capture.ai.llm.requests.post")
	def test_truncates_very_long_ocr_text(self, post):
		post.return_value = ollama_response(content="{}")

		self.client.extract_receipt("x" * 20_000)

		self.assertLess(len(post.call_args.kwargs["json"]["messages"][-1]["content"]), 6_100)

	@patch("receipt_capture.ai.llm.requests.post")
	def test_explains_a_missing_model(self, post):
		post.return_value = ollama_response(status=404)

		with self.assertRaisesRegex(LLMError, "ollama pull qwen2.5:1.5b"):
			self.client.extract_receipt("text")

	@patch("receipt_capture.ai.llm.requests.post", side_effect=requests.Timeout)
	def test_timeout(self, _post):
		with self.assertRaisesRegex(LLMError, "within 30s"):
			self.client.extract_receipt("text")

	@patch("receipt_capture.ai.llm.requests.post", side_effect=requests.ConnectionError("refused"))
	def test_unreachable(self, _post):
		with self.assertRaisesRegex(LLMError, "Could not reach Ollama"):
			self.client.extract_receipt("text")

	@patch("receipt_capture.ai.llm.requests.post")
	def test_non_json_content(self, post):
		post.return_value = ollama_response(content="Sure! Here is the receipt:")

		with self.assertRaisesRegex(LLMError, "non-JSON"):
			self.client.extract_receipt("text")

	@patch("receipt_capture.ai.llm.requests.post")
	def test_server_error(self, post):
		post.return_value = ollama_response(status=500)

		with self.assertRaisesRegex(LLMError, "HTTP 500"):
			self.client.extract_receipt("text")


class TestHealth(unittest.TestCase):
	@patch("receipt_capture.ai.llm.requests.get")
	def test_model_available_with_or_without_tag(self, get):
		get.return_value = ollama_response(
			payload={"models": [{"name": "qwen2.5:1.5b"}, {"name": "llama3.1:latest"}]}
		)

		self.assertTrue(OllamaClient("http://o", "qwen2.5:1.5b").health()["ok"])
		self.assertTrue(OllamaClient("http://o", "llama3.1").health()["ok"])
		missing = OllamaClient("http://o", "mistral").health()
		self.assertFalse(missing["ok"])
		self.assertIn("not pulled", missing["error"])

	@patch("receipt_capture.ai.llm.requests.get", side_effect=requests.ConnectionError("refused"))
	def test_unreachable(self, _get):
		result = OllamaClient("http://o", "m").health()

		self.assertFalse(result["ok"])
		self.assertIn("unreachable", result["error"])
