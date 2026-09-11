# Architecture Overview

A text description is provided here in place of `architecture.png`, since binary image
generation isn't available in this environment. Recreate this as a diagram for the slide deck.

## Components and Flow

```
[ Browser: frontend (Vercel) ]
        |
        | HTTPS fetch() with CORS
        v
[ FastAPI backend (Render) ]
        |
        |-- POST /api/v1/documents/process
        |        |
        |        v
        |   [document_validation_service] -- rejects bad files early
        |        |
        |        v
        |   [ocr_service] -- PyMuPDF for native PDF text, pytesseract for
        |        |            scanned PDFs/images
        |        v
        |   [extraction_service] -- calls an OpenAI-compatible LLM API,
        |        |                  returns structured JSON per document type
        |        v
        |   [financial_validation_service] -- recomputes totals/checks
        |        |                            from extracted values only
        |        v
        |   [document_service] -- assembles the response envelope
        |        |
        |        v
        |   [document_repository] -- persists to SQLite via SQLAlchemy
        |
        |-- GET /api/v1/documents/{name}      -> repository lookup
        |-- GET /api/v1/documents             -> repository list
        |-- GET /api/v1/health                -> liveness check
        v
[ SQLite database (document_intelligence.db) ]
```

## Layering

- **api/routes** — HTTP boundary only: parses requests, calls services, returns responses.
- **services** — all business logic (validation, OCR, extraction, financial checks, orchestration).
- **repositories** — the only layer that touches the database, via SQLAlchemy sessions.
- **schemas** — Pydantic models define the request/response contracts and are shared across
  routes and services so the API surface stays consistent.
- **models** — SQLAlchemy ORM table definitions.

## Deployment Topology

- **backend/** deploys independently to Render as a Python web service (`render.yaml`
  included). SQLite is file-based on the instance disk, which is sufficient for this
  case study; a production deployment would move to a managed Postgres instance.
- **frontend/** deploys independently to Vercel as a static site (`vercel.json`
  included) with zero build step. It talks to the backend only through `fetch()` calls
  gated by CORS, using the base URL configured in `frontend/js/config.js`.
