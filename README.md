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

Open http://localhost:8080 and log in as `Administrator` with your `ADMIN_PASSWORD`. First start takes a few minutes: it creates the site, installs ERPNext and this app, and downloads the model. Then:

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
# Tests: 53 tests (extraction, Ollama client, OCR on generated images, and ERPNext integration)
bench --site your.site set-config allow_tests true
bench --site your.site run-tests --app receipt_capture

# Lint and format (Frappe's Ruff configuration in pyproject.toml)
ruff check . && ruff format --check .
```

CI (`.github/workflows/ci.yml`) runs Ruff, then builds the Docker image, creates a fresh ERPNext site with the app, and runs the full test suite.

### License

MIT
