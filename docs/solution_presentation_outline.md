# Solution Presentation Outline

## 1. Problem Statement
- Financial back-offices receive invoices, balance sheets, P&L statements, and cash
  flow statements as unstructured PDFs/images.
- Manual re-keying is slow and error-prone; totals often don't get cross-checked.

## 2. Solution Summary
- A document intelligence platform that extracts structured data from all four
  document types and independently re-validates the reported totals.
- Split deployment: FastAPI backend (Render) + static vanilla-JS frontend (Vercel).

## 3. Architecture
- Walk through `docs/architecture.md` diagram.
- Emphasize the layered backend: routes → services → repository → database.

## 4. Extraction Pipeline
- File validation (type, corruption, page limit) before any processing.
- Native PDF text via PyMuPDF; OCR fallback via Tesseract for scanned documents/images.
- LLM call (provider-agnostic, OpenAI-compatible) turns raw text into schema-conforming
  JSON, with every field carrying `source_text`, `page_number`, and `confidence`.
- Null-if-absent policy: nothing is invented.

## 5. Financial Validation Engine
- Deterministic, code-based recomputation of each check — not another LLM call.
- Per document type: line-item math, subtotal/tax/total reconciliation, balance sheet
  equation, P&L waterfall, cash flow reconciliation.
- Tolerance-based PASS/FAIL, NOT_APPLICABLE when required inputs are missing.

## 6. API Design
- Four endpoints: process, get-by-name, list, health.
- Consistent success and error envelopes; Swagger docs auto-generated at `/docs`.

## 7. Frontend
- Strict black-and-white design system — status conveyed via typography/borders, not color.
- Upload → dashboard → detail view → raw JSON, in that order.

## 8. Testing & Quality
- pytest coverage: file validation, financial calculations, and a full API round trip.
- Structured logging, no leaked stack traces, consistent error codes.

## 9. Known Limitations & Production Roadmap
- SQLite → managed Postgres; synchronous processing → background job queue for large
  batches; single LLM call → add a verification/self-consistency pass; add auth and
  rate limiting before any public exposure.

## 10. Q&A
