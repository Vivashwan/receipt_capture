## Receipt Capture for ERPNext

Turn a photo of a shop receipt into a draft **Purchase Invoice** in ERPNext. The image is cleaned up with **OpenCV**, read with **Tesseract OCR**, and structured by a **local LLM running on Ollama**, so receipt data never leaves your servers. Every extraction is validated before anyone can invoice it.

```
Receipt photo ─▶ OpenCV cleanup ─▶ Tesseract OCR ─▶ Ollama (JSON schema) ─▶ validation ─▶ Receipt Capture ─▶ draft Purchase Invoice
                 (grayscale, upscale,                   local model,          (amounts, dates,    (review in       (supplier matched
                  denoise, threshold,                    temperature 0)        totals, grounding)  ERPNext)          or created)
                  deskew)
```

Built on **Frappe v15 / ERPNext v15**.

### What it adds to ERPNext

| Piece | What it does |
|---|---|
| **Receipt Capture** DocType | Upload a receipt image; extraction runs in a background job and fills vendor, bill number, date, line items, tax and total. Status: Pending → Processing → Extracted / Needs Review / Failed → Invoiced |
| **Receipt Capture Item** (child table) | Extracted line items; amount/rate kept consistent on edit |
| **Receipt AI Settings** (single) | Ollama URL and model, OCR language, auto-extract, supplier auto-create, default expense item, tax account. *Test Ollama Connection* button |
| Client script | Buttons for *Extract with AI*, *Create Purchase Invoice*; live refresh via a realtime event when the background job finishes; review warnings shown in the form header |
| **Receipt Capture Summary** script report | Per-supplier receipts, invoiced vs pending amounts, items needing attention, average extraction time, with a stacked chart and summary cards |
| **Receipt Capture Detail** print format | Clean Jinja print of the extracted receipt with the source image |
| `bench receipt-ai` CLI | `health` (Tesseract + model check), `reprocess --status Failed`, `stats` |
| Scheduler | Hourly job marks receipts stuck in *Processing* (e.g. after a worker crash) as *Failed* so they can be retried |

Purchase Invoices are always created as **drafts** for an accountant to review and submit, posted on the receipt's date, with the receipt image attached for audit.

### Run it with Docker

```bash
cp .env.example .env        # set DB_ROOT_PASSWORD and ADMIN_PASSWORD
docker compose up -d --build
```

Open **http://erp.localhost:8080** (the site name, `SITE_NAME`; `*.localhost` resolves to your machine) and log in as `Administrator` with your `ADMIN_PASSWORD`. Use the site name rather than `localhost`: Frappe's realtime server only accepts connections whose host matches the site, and without it the form won't update live when extraction finishes. First start takes a few minutes: it creates the site, installs ERPNext and this app, and downloads the model. Then:

1. Complete the ERPNext setup wizard (company, fiscal year).
2. In **Receipt AI Settings**, choose a non-stock **Default Expense Item** (and optionally a Tax Account), then click *Test Ollama Connection*.
3. Create a **Receipt Capture**, attach a receipt photo, and save.

The stack follows [frappe_docker](https://github.com/frappe/frappe_docker): MariaDB, Redis, gunicorn, background workers (extraction runs on the `long` queue), scheduler, websocket and nginx, plus Ollama. `alpine/ollama` is a ~40 MB CPU-only build; on a GPU host set `OLLAMA_IMAGE=ollama/ollama`.

**Choosing a model:** `qwen2.5:1.5b` (the default) runs on CPU in about 1.5 GB of RAM. Larger models such as `llama3.1:8b` are more accurate on messy receipts but need more memory. Change `OLLAMA_MODEL` in `.env`, or the model in Receipt AI Settings.

### Install into an existing bench

```bash
sudo apt install tesseract-ocr tesseract-ocr-eng
bench get-app https://github.com/Vivashwan/receipt_capture
bench --site your.site install-app receipt_capture
```

Then run Ollama somewhere reachable and set its URL in Receipt AI Settings.

### Design decisions

- **Local LLM, not a cloud API.** Receipts contain supplier, pricing and sometimes personal data. Ollama keeps them on your infrastructure, with no per-call cost.
- **Schema-constrained output.** The JSON schema is passed to Ollama's `format` option, at temperature 0, so even a small model returns parseable, deterministic JSON.
- **Never trust the model's numbers.** `ai/extraction.py` normalises amounts (`₹1,234.50`, `Rs. 12,34,567.00`) and day-first Indian dates, then:
  - drops summary rows (TOTAL, Sub Total, Round Off) and moves GST/CGST/SGST/VAT rows into tax. Small models often list these as purchased items;
  - checks that line items plus tax add up to the total;
  - **grounding check:** flags any amount that doesn't appear in the OCR text, which catches misread or invented figures.

  Anything suspicious puts the receipt in *Needs Review* with a specific note, instead of silently producing a wrong invoice.
- **Background jobs, not request threads.** OCR and the model take seconds, so extraction runs on a worker. Jobs are queued after the transaction commits and deduplicated per receipt. The form updates via a realtime event.
- **MariaDB.** ERPNext officially supports only MariaDB, so the stack uses it.

### Measured results (CPU, no GPU)

On a tilted, noisy test receipt (`RICE 320.00 / DAL 160.00 / GST 24.00 / TOTAL 504.00`), run end to end through the background worker:

| Model | Time | Result |
|---|---|---|
| `qwen2.5:1.5b` | 7.6 s | All lines, tax, total and date correct → *Extracted*; draft invoice created |
| `qwen2.5:0.5b` | 3.7 s | Misread rice as 500.00 → caught by the grounding and totals checks → *Needs Review* |

### Development

```bash
# Tests: 55 tests (extraction, Ollama client, OCR on generated images, and ERPNext integration)
bench --site your.site set-config allow_tests true
bench --site your.site run-tests --app receipt_capture

# Lint and format (Frappe's Ruff configuration in pyproject.toml)
ruff check . && ruff format --check .
```

### Browser tests (Selenium WebDriver)

The same 16 user journeys are automated three times: in **Python** (pytest + Selenium, [`e2e/python`](e2e/python)), **JavaScript** (Mocha + `selenium-webdriver`, [`e2e/js`](e2e/js)) and **C#** (NUnit + Selenium WebDriver, [`e2e/dotnet`](e2e/dotnet)). All three run against the real Docker stack, with the real OCR and local model, use the Page Object pattern, and tag Login and Settings as a quick **smoke** subset.

| Suite | What it checks |
|---|---|
| Login | Wrong password is rejected; valid login reaches the desk |
| Receipt AI Settings | *Test Ollama Connection* reports the model as ready |
| Receipt → invoice | Upload a photo → form switches from *Processing* to *Extracted* **live, without a page reload** → vendor, lines, tax and total match the photo, with no TOTAL/GST rows as items → *Create Purchase Invoice* opens a **draft** for ₹504 with GST → receipt is *Invoiced* and locked |
| Unreadable receipt | Blank image → *Failed* with an actionable message → user keys in lines by hand, totals stay in sync, mismatch warning, corrections saved |
| Summary report | Per-supplier counts; failed receipts (no bill date) still appear in a date range |
| Permissions | Accounts User can read settings but not test the connection; a user without an accounts role is refused |

```bash
docker compose up -d --build
docker compose exec backend bench --site erp.localhost execute receipt_capture.e2e_setup.setup_site

export ADMIN_PASSWORD=...
e2e/run-suite.sh python            # or js, dotnet; add --smoke for the smoke subset
```

`e2e/run-suite.sh` is what every CI system calls, and writes JUnit XML for each suite. Without .NET installed, it runs the C# suite in the .NET SDK container.

`setup_site` seeds an Indian company, an expense item, a GST account and two test users. Set `HEADLESS=0` to watch the browser, or `SELENIUM_REMOTE_URL` to use a Selenium Grid. A failing test saves a screenshot, the page HTML and the **browser console** to `artifacts/`. Waits are explicit only, with retries for elements Frappe re-renders, which keeps the suites stable on repeated runs.

Writing these tests found bugs that the Python tests couldn't, because they only run in the browser or across services. All are fixed:

- *Create Purchase Invoice* always failed: the client called the method without `doc`, so Frappe looked for a module-level function.
- The form never updated live: Frappe's realtime server rejected the browser's socket (host vs. origin mismatch behind nginx) and couldn't reach the backend to authenticate it (`webserver_host` was unset).
- Rows a user started typing right after extraction finished were wiped: the app reloaded the form on its own event while Frappe also reloaded it on `doc_update`, and the second reload landed after the edit.
- Failed receipts disappeared from the summary report as soon as a date filter was set, because they have no bill date.
- Users who can't create suppliers got a bare "Not permitted" when invoicing a new vendor; they now get a message saying what to do.
- `docker compose up --build` built the same image once per service, which fails on Docker's classic builder.

### AI failure triage

[`e2e/triage/triage.py`](e2e/triage/triage.py) runs after a failed build. It reads every suite's JUnit XML, pairs each failure with the page and browser console its hook saved plus recent service logs, and asks the stack's own local model (Ollama) to classify it as a **product bug, test bug, environment, test data or flaky** issue, with a likely cause and next step. Known failure signatures (for example `Invalid origin`, a refused connection, a failed login) are matched first and passed to the model as hints, with causes ranked above symptoms. That keeps a 1.5B CPU model accurate: on a run opened at `localhost` it traced *Extraction did not finish* back to the socket origin error in the browser console. The report (`triage.md`, `triage.json`) is advisory: the tool exits 0, falls back to signature matching if the model is down, and has its own unit tests (`python -m unittest discover -s e2e/triage`).

### CI

The same pipeline is defined for three CI systems, and each one runs the suites through `e2e/run-suite.sh`:

- **GitHub Actions** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)): Ruff; the Python tests on a fresh ERPNext site; then the full stack with all three Selenium suites, AI triage on failure, and screenshots, reports and triage uploaded.
- **Jenkins** ([`Jenkinsfile`](Jenkinsfile)): a declarative pipeline with one stage per suite (`catchError`, so every suite reports), JUnit publishing, archived artifacts, a `SMOKE_ONLY` parameter, credentials for passwords, and teardown that keeps the downloaded model.
- **GitLab CI** ([`.gitlab-ci.yml`](.gitlab-ci.yml)): lint and triage self-test in containers, and the e2e job on a shell runner, for merge requests and the default branch, with JUnit reports in the merge request.

### License

MIT
