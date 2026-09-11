# Document Intelligence Platform

Extracts, validates, and stores structured data from four financial document types —
Invoice, Balance Sheet, Profit & Loss, and Cash Flow Statement — from native PDFs,
scanned PDFs, or JPG/PNG images.

## 1. Solution Overview & Architecture

See `docs/architecture.md` for the full diagram and layering explanation. In short:

```
frontend (static HTML/CSS/JS, Vercel) --fetch()--> backend (FastAPI, Render) --> SQLite
```

The backend is layered as `api/routes` → `services` → `repositories` → `models`, with
Pydantic `schemas` defining every request/response contract.

## 2. Tech Stack & Why

| Layer | Choice | Why |
|---|---|---|
| API framework | FastAPI + Uvicorn | async-ready, automatic OpenAPI/Swagger docs, strong Pydantic v2 integration |
| Validation/schemas | Pydantic v2 | single source of truth for request/response shapes |
| PDF text | PyMuPDF (fitz) | fast native text extraction, also used to rasterize scanned pages |
| OCR | pytesseract (Tesseract) | free, self-hostable, no external API dependency for OCR itself |
| Structured extraction | any OpenAI-compatible LLM API | swappable via env vars, so any provider/key can be plugged in |
| Database | SQLite via SQLAlchemy, repository pattern | zero-ops for a case study; repository layer makes swapping to Postgres a one-line change |
| Frontend | Plain HTML/CSS/vanilla JS | matches the no-build-step requirement, deploys as a static site on Vercel |
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

Copy the environment file and fill in your LLM key:

```bash
cp ../.env.example .env
# edit .env and set LLM_API_KEY
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

No build step — just serve the static files. Two easy options:

```bash
cd frontend
python -m http.server 5500
# open http://localhost:5500
```

or use the VS Code "Live Server" extension pointed at `frontend/index.html`.

By default `frontend/js/config.js` points at `http://localhost:8000` when running on
`localhost`, and at a placeholder production URL otherwise — update that placeholder
once the backend is deployed (see Deployment section).

## 4. .env.example Explained

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `development` or `production`, informational |
| `DATABASE_URL` | SQLAlchemy connection string, defaults to a local SQLite file |
| `CORS_ALLOWED_ORIGIN` | The exact origin allowed to call the API (your frontend's URL) |
| `MAX_UPLOAD_PAGES` | Hard cap on pages per document (spec requires rejecting >3) |
| `MAX_UPLOAD_SIZE_MB` | Hard cap on upload size |
| `LLM_PROVIDER` | Label for which provider you're using (informational, base URL drives behavior) |
| `LLM_BASE_URL` | Base URL of an OpenAI-compatible `/chat/completions` endpoint |
| `LLM_API_KEY` | Your API key for that provider — required for extraction to work |
| `LLM_MODEL` | Model name to request |
| `TESSERACT_CMD` | Path to the tesseract binary if it's not on PATH |
| `FINANCIAL_TOLERANCE_PERCENT` | Allowed variance percentage before a validation check is marked FAIL |

## 5. API Examples

**Process a document**

```bash
curl -X POST http://localhost:8000/api/v1/documents/process \
  -F "file=@invoice.pdf" \
  -F "document_type=invoice"
```

**Get a processed document by name**

```bash
curl http://localhost:8000/api/v1/documents/invoice.pdf
```

**List all processed documents**

```bash
curl http://localhost:8000/api/v1/documents
```

**Health check**

```bash
curl http://localhost:8000/api/v1/health
```

Full request/response schemas are always up to date at `/docs`.

## 6. OCR and LLM Services Used

- **OCR**: Tesseract via `pytesseract`, only invoked when a PDF has no extractable
  native text layer (i.e. it's a scan) or the upload is a JPG/PNG. Native PDF text is
  read directly with PyMuPDF, which is faster and more accurate than OCR when available.
- **LLM extraction**: a single call to any OpenAI-compatible `/chat/completions`
  endpoint, with a strict per-document-type JSON schema in the prompt. The model is
  instructed to return `null` for anything not actually present in the text rather
  than inferring a value.

## 7. Financial Validation Rules & Tolerance

All checks are computed in code from the extracted values themselves — never by
asking the LLM to "check its own math." Each check reports `NOT_APPLICABLE` when a
required input is missing, rather than guessing. Default tolerance is **1%**,
configurable via `FINANCIAL_TOLERANCE_PERCENT`.

- **Invoice**: `quantity × unit_price ≈ line amount` per line item; `sum(line amounts) ≈ subtotal`;
  `subtotal + tax − discount ≈ total`; `cash_paid − total ≈ change`.
- **Balance Sheet**: `total_liabilities + total_equity ≈ total_assets`, per period.
- **Profit & Loss**: `revenue − cost_of_sales ≈ gross_profit`; `gross_profit − operating_expenses ≈ operating_profit`;
  `operating_profit − tax ≈ net_profit`, per period.
- **Cash Flow**: `operating + investing + financing ≈ net_change_in_cash`; `opening_cash + net_change_in_cash ≈ closing_cash`, per period.

Bracketed/parenthesized amounts (e.g. `(6,200.00)`) are parsed as negative numbers
throughout.

## 8. Database Approach

SQLite via SQLAlchemy Core/ORM, accessed exclusively through
`repositories/document_repository.py` (repository pattern). Each processing run is
stored as a new row keyed by `document_name`; `GET /documents/{name}` returns the most
recent one. This keeps a full history while the "latest result" semantics required by
the spec still work. Swapping to Postgres is just a `DATABASE_URL` change.

## 9. Known Limitations

- Processing is synchronous — a large/slow OCR+LLM call blocks the request until done.
- SQLite is single-file and not suited to concurrent write-heavy production traffic.
- The LLM extraction is a single pass with no self-consistency or human-in-the-loop review step.
- No authentication/authorization on the API — anyone with the URL can upload and read documents.
- No malware/antivirus scanning on uploaded files.

## 10. What Would Change for Production

- Move processing to a background job queue (e.g. Celery/RQ) with a polling or webhook
  status endpoint instead of a synchronous request.
- Move the database to managed Postgres with proper migrations (Alembic).
- Add authentication (API keys or OAuth), per-tenant isolation, and rate limiting.
- Add a second LLM pass or rules engine to cross-check extraction confidence before
  trusting a value in downstream financial reporting.
- Add virus scanning and stricter file-content sniffing beyond extension checks.
- Add structured, centralized log aggregation and alerting.

## 11. AI Tools Used

This codebase was built with the assistance of an AI coding assistant (Claude), which
generated the initial implementation of the backend services, API routes, frontend, and
tests based on a detailed specification. All code was reviewed and the automated test
suite (`pytest`) was run to confirm the file-validation, financial-calculation, and
API-flow tests pass before delivery.

## Deployed URLs

- Backend (Render): `https://<your-backend-service>.onrender.com` *(fill in after deploying)*
- Frontend (Vercel): `https://<your-frontend-project>.vercel.app` *(fill in after deploying)*
