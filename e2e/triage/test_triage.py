"""python -m unittest discover -s e2e/triage (standard library only, like triage.py)."""

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import ClassVar

import triage

PYTEST_JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="2" failures="1">
  <testcase classname="tests.test_01_login" name="test_logs_in_with_valid_credentials_and_opens_the_desk">
    <failure message="selenium.common.exceptions.TimeoutException: Message: Login as Administrator did not reach the desk">Traceback ...</failure>
  </testcase>
  <testcase classname="tests.test_01_login" name="test_rejects_a_wrong_password_and_stays_on_the_login_page"/>
</testsuite></testsuites>"""

MOCHA_JUNIT = """<testsuite name="Mocha Tests" tests="1" failures="1" errors="0" skipped="0">
<testcase classname="Receipt photo to draft Purchase Invoice" name="fills vendor, line items, tax and total from the photo">
<failure>Expected values to be strictly equal: 480 !== 504
AssertionError [ERR_ASSERTION]</failure></testcase>
</testsuite>"""

TRX = """<?xml version="1.0" encoding="utf-8"?>
<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010"><Results>
  <UnitTestResult testName="FailsWithAReasonTheUserCanActOn" outcome="Failed">
    <Output><ErrorInfo><Message>Extraction did not finish</Message><StackTrace>at WaitForExtraction()</StackTrace></ErrorInfo></Output>
  </UnitTestResult>
  <UnitTestResult testName="LogsIn" outcome="Passed"/>
</Results></TestRun>"""

PAGE = """<html><head><script>var x = "modal-title";</script></head><body>
  <div class="page-head"><span class="indicator-pill red">Failed</span></div>
  <div class="modal show"><div class="modal-title">Not permitted</div>
  <div class="modal-body"><p>You need the <b>Accounts User</b> role</p></div></div>
  <div class="hidden-noise">Lots of desk chrome</div>
</body></html>"""


class FakeOllama(BaseHTTPRequestHandler):
	reply: ClassVar[dict] = {}
	requests: ClassVar[list] = []

	def do_POST(self):
		body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
		FakeOllama.requests.append(body)
		data = json.dumps({"message": {"content": json.dumps(FakeOllama.reply)}}).encode()
		self.send_response(200)
		self.send_header("Content-Type", "application/json")
		self.end_headers()
		self.wfile.write(data)

	def log_message(self, *args):
		pass


class TriageTest(unittest.TestCase):
	def setUp(self):
		self.dir = Path(tempfile.mkdtemp())
		(self.dir / "py").mkdir()
		(self.dir / "py" / "junit.xml").write_text(PYTEST_JUNIT)
		(self.dir / "js.xml").write_text(MOCHA_JUNIT)
		(self.dir / "results.trx").write_text(TRX)

	def test_reads_failures_from_junit_and_trx_and_skips_passes(self):
		failures = triage.read_results([str(self.dir / "**" / "*.xml"), str(self.dir / "*.trx")])

		self.assertEqual(
			sorted(f.test for f in failures),
			[
				"FailsWithAReasonTheUserCanActOn",
				"Receipt photo to draft Purchase Invoice :: fills vendor, line items, tax and total from the photo",
				"tests.test_01_login :: test_logs_in_with_valid_credentials_and_opens_the_desk",
			],
		)
		trx = next(f for f in failures if f.test == "FailsWithAReasonTheUserCanActOn")
		self.assertEqual(trx.message, "Extraction did not finish")

	def test_page_text_keeps_dialogs_and_status_but_not_scripts_or_noise(self):
		text = triage.page_text(PAGE)

		self.assertIn("Not permitted", text)
		self.assertIn("Accounts User", text)
		self.assertIn("Failed", text)
		self.assertNotIn("Lots of desk chrome", text)
		self.assertNotIn("var x", text)

	def test_pairs_a_failure_with_the_page_its_hook_saved(self):
		artifacts = self.dir / "e2e" / "python" / "artifacts"
		artifacts.mkdir(parents=True)
		(
			artifacts / "tests-test_01_login-py-test_logs_in_with_valid_credentials_and_opens_the_desk.html"
		).write_text(PAGE)
		failure = triage.Failure(
			"s", "tests.test_01_login :: test_logs_in_with_valid_credentials_and_opens_the_desk", "m"
		)

		triage.attach_artifacts([failure], [str(self.dir / "e2e")])

		self.assertTrue(failure.artifact.endswith(".html"))
		self.assertIn("Not permitted", failure.page_text)

	def test_known_signatures_become_hints(self):
		failure = triage.Failure("s", "t", "TimeoutException: Login as Administrator did not reach the desk")

		hints = triage.match_signatures(failure, logs="websocket | Invalid origin.")

		self.assertEqual([h["category"] for h in hints], ["test-data", "environment"])
		self.assertEqual(hints[1]["seen_in"], "logs")

	def test_puts_the_cause_before_the_symptom_it_explains(self):
		failure = triage.Failure("s", "t", "TimeoutException: Extraction did not finish")
		failure.console = 'SEVERE desk.bundle.js "Error connecting to socket.io:" "Invalid origin"'

		hints = triage.match_signatures(failure, logs="")

		self.assertEqual(
			[(h["kind"], h["seen_in"]) for h in hints], [("cause", "browser console"), ("symptom", "error")]
		)
		failure.hints = hints
		self.assertIn("realtime", triage.fallback_analysis(failure)["summary"])

	def test_falls_back_to_signatures_when_the_model_is_unreachable(self):
		failures = [triage.Failure("s", "t", "Extraction did not finish")]

		triage.analyse(failures, "", "http://127.0.0.1:9", "m", timeout=2, limit=10)

		self.assertEqual(failures[0].analysis["category"], "environment")
		self.assertEqual(failures[0].analysis["source"], "signature")

	def test_asks_the_model_with_a_json_schema_and_writes_the_report(self):
		FakeOllama.reply = {
			"category": "product-bug",
			"summary": "Total read as 480 instead of 504",
			"likely_cause": "GST line dropped",
			"next_step": "Check tax parsing",
			"confidence": "medium",
		}
		FakeOllama.requests = []
		server = HTTPServer(("127.0.0.1", 0), FakeOllama)
		threading.Thread(target=server.serve_forever, daemon=True).start()
		self.addCleanup(server.shutdown)
		out = self.dir / "triage"

		code = triage.main(
			[
				"--results",
				str(self.dir / "js.xml"),
				"--artifacts",
				str(self.dir),
				"--ollama-url",
				f"http://127.0.0.1:{server.server_port}",
				"--out",
				str(out),
			]
		)

		self.assertEqual(code, 0)
		self.assertEqual(
			FakeOllama.requests[0]["format"]["properties"]["category"]["enum"], triage.CATEGORIES
		)
		self.assertIn("480 !== 504", FakeOllama.requests[0]["messages"][1]["content"])
		report = (self.dir / "triage.md").read_text()
		self.assertIn("**1** product-bug", report)
		self.assertIn("GST line dropped", report)
		self.assertEqual(json.loads((self.dir / "triage.json").read_text())[0]["analysis"]["source"], "model")

	def test_rejects_a_category_outside_the_schema(self):
		FakeOllama.reply = {
			"category": "cosmic-rays",
			"summary": "",
			"likely_cause": "",
			"next_step": "",
			"confidence": "low",
		}
		server = HTTPServer(("127.0.0.1", 0), FakeOllama)
		threading.Thread(target=server.serve_forever, daemon=True).start()
		self.addCleanup(server.shutdown)
		failures = [triage.Failure("s", "t", "AssertionError")]

		triage.analyse(failures, "", f"http://127.0.0.1:{server.server_port}", "m", timeout=5, limit=10)

		self.assertEqual(failures[0].analysis["source"], "none")


if __name__ == "__main__":
	unittest.main()
