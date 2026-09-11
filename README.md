# Document Intelligence Platform

Extracts, validates, and stores structured data from four financial document types —
Invoice, Balance Sheet, Profit & Loss, and Cash Flow Statement — from native PDFs,
scanned PDFs, or JPG/PNG images.

**Live Frontend:** https://intelligent-document-extraction.vercel.app 
<hr>
**Live Backend API:** https://intelligent-document-extraction-ub14.onrender.com
<hr>
**Swagger / OpenAPI Docs:** https://intelligent-document-extraction-ub14.onrender.com/docs
<hr>
**GitHub Repository:** https://github.com/princebhandarii/Intelligent-Document-Extraction
<hr>

> Note: the backend runs on Render's free tier, which spins down after inactivity.
> The first request after idle time can take 30–60 seconds to respond — this is a
> known platform limitation, not an application error. See Known Limitations below.

## 1. Solution Overview & Architecture

```
frontend (static HTML/CSS/JS, Vercel)
   │  fetch()
   ▼
backend (FastAPI + Uvicorn, Docker, Render)
   │
   ├── file validation (type, size, page count, integrity)
   ├── OCR / text extraction (PyMuPDF for native PDFs, Tesseract for scans & images)
   ├── LLM extraction (Groq, OpenAI-compatible /chat/completions endpoint)
   ├── quantity reconciliation (derives quantity from amount ÷ unit_price when OCR misreads it)
   ├── financial validation (formulas computed in code, never by the LLM)
   └── persistence (SQLAlchemy → Postgres)
           │
           ▼
     Neon (managed Postgres, serverless)
```

<img width="1088" height="560" alt="Architecture" src="https://github.com/user-attachments/assets/1b72651c-d820-4467-a83f-a72986a365cb" />



The backend is layered as `api/routes` → `services` → `repositories` → `models`, with
Pydantic `schemas` defining every request/response contract. See `docs/architecture.md`
for the full diagram.

## 2. Tech Stack & Why

| Layer | Choice | Why |
|---|---|---|
| API framework | FastAPI + Uvicorn | async-ready, automatic OpenAPI/Swagger docs, strong Pydantic v2 integration |
| Validation/schemas | Pydantic v2 | single source of truth for request/response shapes |
| PDF text | PyMuPDF (fitz) | fast native text extraction; used first, before falling back to OCR |
| OCR | pytesseract (Tesseract) | free, self-hostable, no external API key or rate limits |
| Structured extraction | Groq (Llama-family model via OpenAI-compatible API) | free tier with no card required, fast inference, drop-in OpenAI-style request format |
| Database | PostgreSQL (Neon, serverless) via SQLAlchemy, repository pattern | free tier, persists independently of the backend host, no cold-start data loss |
| Backend hosting | Render (Docker) | Dockerfile installs Tesseract as a system package; free tier is Docker-native |
| Frontend hosting | Vercel | zero-config static hosting, instant global CDN, no cold starts |
| Frontend | Plain HTML/CSS/vanilla JS | matches the no-build-step requirement, deploys as a static site |
| Testing | pytest | file validation, financial math, and a full API round trip are covered |

## 3. Local Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Install Tesseract (required for OCR on scanned documents/images):

```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract

# Windows: install from https://github.com/UB-Mannheim/tesseract/wiki
# and set TESSERACT_CMD in .env to the full path of tesseract.exe
```

Copy the environment file and fill in your own values:

```bash
cp ../.env.example .env
# edit .env: set DATABASE_URL (a Postgres connection string, e.g. from neon.tech)
# and LLM_API_KEY (a free key from console.groq.com)
```

Run the server:

```bash
uvicorn app.main:app --reload --port 8000
```

Swagger docs: http://localhost:8000/docs

Run tests:

```bash
pytest
```

### Frontend

No build step — just serve the static files:

```bash
cd frontend
python3 -m http.server 5500
# open http://localhost:5500
```

`frontend/js/config.js` points at `http://localhost:8000` when running on `localhost`,
and at the deployed Render URL otherwise.

## 4. .env.example Explained

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `development` or `production`, informational |
| `DATABASE_URL` | SQLAlchemy Postgres connection string (e.g. from Neon) |
| `CORS_ALLOWED_ORIGIN` | The exact origin allowed to call the API (the deployed frontend's URL) |
| `MAX_UPLOAD_PAGES` | Hard cap on pages per document (spec requires rejecting >3) |
| `MAX_UPLOAD_SIZE_MB` | Hard cap on upload size |
| `LLM_PROVIDER` | Label for which provider is in use (informational) |
| `LLM_BASE_URL` | Base URL of the OpenAI-compatible `/chat/completions` endpoint (Groq) |
| `LLM_API_KEY` | API key for the LLM provider — required for extraction to work |
| `LLM_MODEL` | Model name to request (e.g. `openai/gpt-oss-120b` on Groq) |
| `TESSERACT_CMD` | Path to the tesseract binary if it's not on PATH |
| `FINANCIAL_TOLERANCE_PERCENT` | Allowed variance percentage before a validation check is marked FAIL |

## 5. API Examples

**Process a document**

```bash
curl -X POST https://intelligent-document-extraction-ub14.onrender.com/api/v1/documents/process \
  -F "file=@invoice.pdf" \
  -F "document_type=invoice"
```

**Get a processed document by name**

```bash
curl https://intelligent-document-extraction-ub14.onrender.com/api/v1/documents/invoice.pdf
```

**List all processed documents**

```bash
curl https://intelligent-document-extraction-ub14.onrender.com/api/v1/documents
```

**Health check**

```bash
curl https://intelligent-document-extraction-ub14.onrender.com/api/v1/health
```

Full request/response schemas are always up to date at `/docs`.

## 6. OCR and LLM Services Used

- **OCR**: Tesseract via `pytesseract`, invoked when a PDF has no extractable native
  text layer (i.e. it's a scan) or the upload is a JPG/PNG. Native PDF text is read
  directly with PyMuPDF first, which is faster and more accurate than OCR when available.
- **LLM extraction**: a single call to Groq's OpenAI-compatible `/chat/completions`
  endpoint (free tier, no card required), using `response_format: json_object` to
  force valid JSON and a strict per-document-type schema in the prompt. The model is
  instructed to return `null` for anything not actually present in the text rather
  than inferring a value, and to preserve the document's original numeric formatting
  (comma vs. dot decimal separators) alongside a normalized numeric value.
- **Quantity reconciliation**: a small post-processing step (`reconciliation_service.py`)
  cross-checks each line item's `quantity × unit_price ≈ amount`. If the OCR/LLM
  reading of quantity doesn't reconcile but a clean whole-number quantity can be
  derived from the already-correct `amount` and `unit_price`, it corrects the
  quantity — since those two values are already grounded in the same row.

## 7. Financial Validation Rules & Tolerance

All checks are computed in code from the extracted values themselves — never by
asking the LLM to "check its own math." Each check reports `NOT_APPLICABLE` when a
required input is missing, rather than guessing. Default tolerance is **1%**,
configurable via `FINANCIAL_TOLERANCE_PERCENT`.

- **Invoice**: `quantity × unit_price ≈ line amount` per line item; `sum(line amounts) ≈ subtotal`;
  `subtotal + tax + shipping − discount ≈ total`; `cash_paid − total ≈ change`.
- **Balance Sheet**: `total_liabilities + total_equity ≈ total_assets`, per period.
- **Profit & Loss**: `revenue − cost_of_sales ≈ gross_profit`; `gross_profit − operating_expenses ≈ operating_profit`;
  `operating_profit − tax ≈ net_profit`, per period.
- **Cash Flow**: `operating + investing + financing ≈ net_change_in_cash`; `opening_cash + net_change_in_cash ≈ closing_cash`, per period.

Bracketed/parenthesized amounts (e.g. `(6,200.00)`) are parsed as negative numbers.
Both comma-as-decimal (European, e.g. `138,90`) and comma-as-thousands (e.g. `1,234.56`)
number formats are detected and normalized before any calculation.

## 8. Database Approach

PostgreSQL (hosted on Neon, a free serverless Postgres provider), accessed exclusively
through `repositories/document_repository.py` (repository pattern) via SQLAlchemy.
Each processing run is stored as a new row keyed by `document_name`;
`GET /documents/{name}` returns the most recent one. This keeps a full history while
the "latest result" semantics required by the spec still work. Using a managed
Postgres instance (rather than local SQLite) means processed data persists
independently of the backend's own hosting lifecycle.

## 9. Known Limitations

- Processing is synchronous — a large/slow OCR+LLM call blocks the request until done.
- Backend is on Render's free tier, which spins down after inactivity; the first
  request after idle time can take 30–60 seconds.
- OCR output can vary slightly between runs on the same image, since Tesseract's
  reading is not perfectly deterministic on lower-quality scans.
- Quantity reconciliation only handles the simple `quantity × unit_price ≈ amount`
  case — it will not fix every possible OCR misread.
- A single free LLM provider (Groq) is used, with no automatic failover if it's
  unavailable or rate-limited.
- No authentication/authorization on the API — anyone with the URL can upload and
  read documents.
- No malware/antivirus scanning on uploaded files.

## 10. What Would Change for Production

- Move processing to a background job queue (e.g. Celery/RQ) with a polling or
  webhook status endpoint instead of a synchronous request.
- Move to a paid hosting tier (or an always-on host) to eliminate cold starts.
- Add a second LLM provider as a fallback, and/or a self-consistency pass for
  higher-stakes extractions.
- Add authentication (API keys or OAuth), per-tenant isolation, and rate limiting.
- Add virus scanning and stricter file-content sniffing beyond extension checks.
- Add structured, centralized log aggregation and alerting.
- Broaden currency/locale handling beyond the comma/dot decimal normalization
  currently implemented.



## 11. AI Tools Used

An AI coding assistant was used throughout the development of this project. Specific
areas where it was used:

- **Architecture & project structure**: designing the layered backend structure
  (api/routes → services → repositories → models), and the overall
  frontend/backend/database separation.
- **Backend implementation**: writing the FastAPI routes, Pydantic schemas, OCR
  service (PyMuPDF + Tesseract), LLM extraction service and prompt design, financial
  validation logic, and the SQLAlchemy repository layer.
- **Bug fixing & debugging**: diagnosing and fixing issues found during testing,
  including a numeric-parsing bug (comma vs. dot decimal separators), a line-item
  extraction gap, a missing shipping-charge field in the total-validation formula,
  and a quantity-misread reconciliation step.
- **Frontend implementation**: writing the HTML/CSS/JavaScript for the upload form,
  dashboard, and result-detail view, including the logic to render extracted fields,
  line items, and validation results from the API response.
- **Deployment troubleshooting**: resolving a missing Postgres driver
  (`psycopg2-binary`) in the Docker build, a duplicated API path in the frontend
  configuration, and CORS configuration between the Render backend and Vercel
  frontend.
- **Documentation**: drafting this README, the architecture diagram description, and
  the solution presentation.


