"""AI-assisted triage of failed end-to-end tests.

Reads the JUnit XML (pytest, Mocha, NUnit) or TRX results the suites write, pairs each
failure with the page HTML its failure hook saved, and asks the stack's own local model
(Ollama) to classify it: product bug, test bug, environment, test data or flaky. Known
failure signatures are matched first and passed to the model as hints, which keeps a small
CPU model on track. Writes triage.md and triage.json.

Advisory only: it exits 0 even if the model is unreachable, so it never hides the real
test result. Standard library only, so any CI agent with Python 3.10+ can run it.

    python e2e/triage/triage.py --results 'e2e/**/junit.xml' 'e2e/**/*.trx' --artifacts e2e --logs compose.log
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path

CATEGORIES = ["product-bug", "test-bug", "environment", "test-data", "flaky", "unknown"]

ANALYSIS_SCHEMA = {
	"type": "object",
	"properties": {
		"category": {"type": "string", "enum": CATEGORIES},
		"summary": {"type": "string"},
		"likely_cause": {"type": "string"},
		"next_step": {"type": "string"},
		"confidence": {"type": "string", "enum": ["low", "medium", "high"]},
	},
	"required": ["category", "summary", "likely_cause", "next_step", "confidence"],
}

# (pattern, category, hint, kind). Searched in the error, the page, the browser console and the
# service logs. A "symptom" says what failed; a "cause" says why. Causes are listed to the model first.
SIGNATURES = [
	(
		r"ERR_CONNECTION_REFUSED|ECONNREFUSED|Connection refused|ERR_NAME_NOT_RESOLVED",
		"environment",
		"The browser or a service could not connect: the stack is down or BASE_URL is wrong.",
		"cause",
	),
	(
		r"502 Bad Gateway",
		"environment",
		"nginx could not reach a backend; after restarting the websocket or backend container, restart frontend too.",
		"cause",
	),
	(
		r"Invalid origin",
		"environment",
		"socket.io rejected the browser's origin, so open forms get no realtime updates; open the site by its name (http://erp.localhost:8080), not localhost.",
		"cause",
	),
	(
		r"session not created|This version of ChromeDriver|cannot find Chrome binary",
		"environment",
		"ChromeDriver and Chrome don't match, or Chrome isn't installed on the agent.",
		"cause",
	),
	(
		r"Invalid Login|did not reach the desk|/login - Failed to load resource: .* 401",
		"test-data",
		"Login failed: the password env vars don't match the site, or the test users were not seeded (e2e_setup).",
		"cause",
	),
	(
		r"Not permitted|PermissionError|No permission",
		"test-data",
		"A permission error: the user's roles are not what the test expects (check the seed script).",
		"cause",
	),
	(
		r"Extraction did not finish",
		"environment",
		"The form never showed a finished status: the job is stuck (check queue-long and the Ollama model) or the form missed the realtime update.",
		"symptom",
	),
	(
		r"StaleElementReference|ElementClickIntercepted|element not interactable",
		"flaky",
		"The page re-rendered during the action; the locator or wait in the page object needs to retry.",
		"cause",
	),
	(
		r"Model .* is not pulled|model .* not found",
		"environment",
		"The Ollama model is missing: run the ollama-pull service.",
		"cause",
	),
]

SYSTEM_PROMPT = """You triage failed end-to-end UI tests of an ERPNext app that reads receipts with OCR and a local LLM.
Classify the failure into exactly one category:
- product-bug: the app behaved wrongly (wrong value, missing button, wrong status) while the environment was healthy.
- test-bug: the test or page object is wrong (bad locator, wrong expectation, missing wait).
- environment: services down, unreachable, misconfigured, slow, or browser/driver problems.
- test-data: missing or wrong seed data, users, roles, passwords or settings.
- flaky: timing-dependent; likely passes on a re-run.
- unknown: not enough evidence.
Known-signature hints are reliable; prefer them when they match. A [cause] hint explains a [symptom] hint:
when both match, likely_cause and next_step must come from the cause. Be concrete and brief:
summary is one sentence, likely_cause names the specific thing, next_step is one action."""


@dataclass
class Failure:
	suite: str
	test: str
	message: str
	details: str = ""
	page_text: str = ""
	console: str = ""
	artifact: str = ""
	hints: list[dict] = field(default_factory=list)
	analysis: dict | None = None


# ---- reading results ----


def parse_junit(path: Path) -> list[Failure]:
	"""JUnit XML as written by pytest (--junitxml), Mocha's xunit reporter and JunitXml.TestLogger."""
	failures = []
	for case in ET.parse(path).getroot().iter("testcase"):
		problem = case.find("failure")
		if problem is None:
			problem = case.find("error")
		if problem is None:
			continue
		classname = case.get("classname", "")
		name = case.get("name", "")
		# Mocha puts the full title in name and the describe block in classname
		test = (
			name if classname and name.startswith(classname) else " :: ".join(filter(None, [classname, name]))
		)
		failures.append(
			Failure(
				suite=path.as_posix(),
				test=test,
				# Mocha's xunit reporter has no message attribute: its first line is the message
				message=(problem.get("message") or (problem.text or "").strip().split("\n")[0]).strip(),
				details=(problem.text or "").strip(),
			)
		)
	return failures


def parse_trx(path: Path) -> list[Failure]:
	"""Visual Studio TRX as written by `dotnet test --logger trx`."""
	ns = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
	failures = []
	for result in ET.parse(path).getroot().iterfind(".//t:UnitTestResult", ns):
		if result.get("outcome") != "Failed":
			continue
		failures.append(
			Failure(
				suite=path.as_posix(),
				test=result.get("testName", ""),
				message=(result.findtext(".//t:ErrorInfo/t:Message", "", ns)).strip(),
				details=(result.findtext(".//t:ErrorInfo/t:StackTrace", "", ns)).strip(),
			)
		)
	return failures


def read_results(patterns: list[str]) -> list[Failure]:
	failures = []
	for pattern in patterns:
		for name in sorted(glob.glob(pattern, recursive=True)):
			path = Path(name)
			if {"node_modules", ".venv"} & set(path.parts):
				continue  # a broad glob like e2e/**/junit.xml also reaches dependencies
			try:
				failures += parse_trx(path) if path.suffix == ".trx" else parse_junit(path)
			except ET.ParseError as error:
				print(f"Skipping unreadable results file {path}: {error}", file=sys.stderr)
	return failures


# ---- what the browser showed ----

# Parts of a Frappe page that explain a failure: dialogs, toasts, the form headline and status
INTERESTING = re.compile(
	r"\b(modal-title|modal-body|alert-message|alert-body|form-message|indicator-pill|title-text)\b"
)


class _PageText(HTMLParser):
	VOID = frozenset(
		{"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
	)

	def __init__(self):
		super().__init__()
		self.stack: list[bool] = []  # per open element: is it (inside) an interesting element?
		self.skip = 0
		self.parts: list[str] = []

	def handle_starttag(self, tag, attrs):
		if tag in ("script", "style"):
			self.skip += 1
		if tag in self.VOID:
			return
		inside = bool(self.stack and self.stack[-1]) or bool(
			INTERESTING.search(dict(attrs).get("class") or "")
		)
		self.stack.append(inside)

	def handle_endtag(self, tag):
		if tag in ("script", "style"):
			self.skip = max(0, self.skip - 1)
		if tag not in self.VOID and self.stack:
			self.stack.pop()

	def handle_data(self, data):
		if not self.skip and self.stack and self.stack[-1] and data.strip():
			self.parts.append(data.strip())


def page_text(html: str, limit: int = 1500) -> str:
	parser = _PageText()
	parser.feed(html)
	seen, lines = set(), []
	for part in parser.parts:
		if part not in seen:
			seen.add(part)
			lines.append(part)
	return " | ".join(lines)[:limit]


def _key(text: str) -> str:
	return re.sub(r"[^a-z0-9]", "", text.lower())


def attach_artifacts(failures: list[Failure], roots: list[str]):
	"""
	Pairs each failure with the page HTML (and browser console, when saved) that its suite's
	failure hook wrote; the file names are sanitized test names.
	"""
	pages = {}
	for root in roots:
		for path in Path(root).glob("**/artifacts/*.html"):
			pages[_key(path.stem)] = path
	for failure in failures:
		test_key = _key(failure.test.split(" :: ")[-1])
		matches = [path for key, path in pages.items() if test_key and test_key in key]
		if matches:
			best = min(matches, key=lambda path: len(path.stem))
			failure.artifact = best.as_posix()
			failure.page_text = page_text(best.read_text(encoding="utf-8", errors="replace"))
			console = best.with_name(f"{best.stem}.console.log")
			if console.exists():
				# Keep the last errors and warnings: the failing request is usually near the end
				lines = console.read_text(encoding="utf-8", errors="replace").splitlines()
				failure.console = "\n".join(
					[line for line in lines if not line.upper().startswith(("INFO", "DEBUG"))][-15:]
				)


# ---- analysis ----


def match_signatures(failure: Failure, logs: str) -> list[dict]:
	hints = []
	sources = (
		("error", f"{failure.message}\n{failure.details}"),
		("page", failure.page_text),
		("browser console", failure.console),
		("logs", logs),
	)
	for source, text in sources:
		for pattern, category, hint, kind in SIGNATURES:
			found = re.search(pattern, text or "")
			if found and not any(h["hint"] == hint for h in hints):
				hints.append(
					{
						"category": category,
						"hint": hint,
						"kind": kind,
						"seen_in": source,
						"match": found.group(0),
					}
				)
	return sorted(hints, key=lambda hint: hint["kind"] != "cause")  # stable: causes first, in source order


def build_prompt(failure: Failure, logs: str) -> str:
	hints = "\n".join(
		f"- [{h['kind']}] [{h['category']}] {h['hint']} (matched {h['match']!r} in {h['seen_in']})"
		for h in failure.hints
	)
	return "\n\n".join(
		[
			f"Test: {failure.test}",
			f"Error: {failure.message[:800]}",
			f"Stack (truncated):\n{failure.details[:1500]}",
			f"What the page showed: {failure.page_text or '(no page capture)'}",
			f"Browser console (errors and warnings):\n{failure.console[-1500:] or '(none captured)'}",
			f"Known-signature hints:\n{hints or '- none matched'}",
			f"Recent service logs (tail):\n{logs[-2000:] or '(none)'}",
		]
	)


def fallback_analysis(failure: Failure) -> dict:
	"""Used when the model is unavailable: the best signature match, or unknown."""
	if failure.hints:
		hint = failure.hints[0]
		return {
			"category": hint["category"],
			"summary": hint["hint"],
			"likely_cause": f"Matched {hint['match']!r} in the {hint['seen_in']}",
			"next_step": hint["hint"],
			"confidence": "medium",
			"source": "signature",
		}
	return {
		"category": "unknown",
		"summary": failure.message[:200] or "No error message",
		"likely_cause": "No known signature matched and the model was unavailable",
		"next_step": "Open the screenshot and page HTML for this test",
		"confidence": "low",
		"source": "none",
	}


def ask_model(url: str, model: str, prompt: str, timeout: int) -> dict:
	payload = {
		"model": model,
		"stream": False,
		"format": ANALYSIS_SCHEMA,
		"options": {"temperature": 0},
		"messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
	}
	request = urllib.request.Request(
		f"{url.rstrip('/')}/api/chat",
		data=json.dumps(payload).encode(),
		headers={"Content-Type": "application/json"},
	)
	with urllib.request.urlopen(request, timeout=timeout) as response:
		content = json.loads(response.read())["message"]["content"]
	analysis = json.loads(content)
	if analysis.get("category") not in CATEGORIES:
		raise ValueError(f"unexpected category {analysis.get('category')!r}")
	return {**analysis, "source": "model"}


def analyse(failures: list[Failure], logs: str, url: str, model: str, timeout: int, limit: int):
	model_ok = True
	for index, failure in enumerate(failures):
		failure.hints = match_signatures(failure, logs)
		if not model_ok or index >= limit:
			failure.analysis = fallback_analysis(failure)
			continue
		try:
			failure.analysis = ask_model(url, model, build_prompt(failure, logs), timeout)
		except (OSError, urllib.error.URLError, ValueError, KeyError, json.JSONDecodeError) as error:
			print(f"Model unavailable ({error}); using signature matching only", file=sys.stderr)
			model_ok = False
			failure.analysis = fallback_analysis(failure)


# ---- report ----


def render_markdown(failures: list[Failure], model: str) -> str:
	if not failures:
		return "## E2E failure triage\n\nNo failed tests. 🎉\n"
	counts = {}
	for failure in failures:
		counts[failure.analysis["category"]] = counts.get(failure.analysis["category"], 0) + 1
	lines = [
		"## E2E failure triage",
		"",
		f"{len(failures)} failed test(s): " + ", ".join(f"**{n}** {c}" for c, n in sorted(counts.items())),
		f"Analysis by the local model `{model}` with known-signature hints. Advisory: check before acting.",
		"",
		"| Test | Category | Confidence | Summary |",
		"| --- | --- | --- | --- |",
	]
	for failure in failures:
		a = failure.analysis
		summary = a["summary"].replace("|", "\\|").replace("\n", " ")
		lines.append(f"| {failure.test} | {a['category']} | {a['confidence']} | {summary} |")
	for failure in failures:
		a = failure.analysis
		error = failure.message[:300].replace("`", "'").replace("\n", " ")
		lines += [
			"",
			f"### {failure.test}",
			"",
			f"- **Category:** {a['category']} ({a['confidence']} confidence, from {a['source']})",
			f"- **Likely cause:** {a['likely_cause']}",
			f"- **Next step:** {a['next_step']}",
			f"- **Error:** `{error}`",
		]
		if failure.artifact:
			lines.append(f"- **Page capture:** `{failure.artifact}`")
		for hint in failure.hints:
			lines.append(f"- **Signature:** [{hint['category']}] {hint['hint']}")
	return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--results", nargs="+", required=True, help="glob(s) of JUnit XML / TRX files")
	parser.add_argument(
		"--artifacts", nargs="*", default=["e2e"], help="dirs searched for failure page captures"
	)
	parser.add_argument("--logs", help="file with recent service logs (e.g. docker compose logs)")
	parser.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
	parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b"))
	parser.add_argument("--timeout", type=int, default=180, help="seconds per model call")
	parser.add_argument(
		"--max-ai", type=int, default=10, help="failures sent to the model; the rest use signatures"
	)
	parser.add_argument(
		"--out", default="triage", help="output path without extension (.md and .json are written)"
	)
	args = parser.parse_args(argv)

	failures = read_results(args.results)
	attach_artifacts(failures, args.artifacts)
	logs = (
		Path(args.logs).read_text(encoding="utf-8", errors="replace")
		if args.logs and Path(args.logs).exists()
		else ""
	)
	analyse(failures, logs, args.ollama_url, args.model, args.timeout, args.max_ai)

	markdown = render_markdown(failures, args.model)
	Path(f"{args.out}.md").write_text(markdown, encoding="utf-8")
	Path(f"{args.out}.json").write_text(json.dumps([asdict(f) for f in failures], indent=2), encoding="utf-8")
	if os.environ.get("GITHUB_STEP_SUMMARY"):
		with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
			summary.write(markdown)
	print(markdown)
	return 0


if __name__ == "__main__":
	sys.exit(main())
