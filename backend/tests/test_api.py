import io

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.services import extraction_service, ocr_service

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def stub_external_calls(monkeypatch):
    monkeypatch.setattr(ocr_service, "extract_text", lambda content, extension: ("Invoice #123 total 100", False))
    monkeypatch.setattr(
        extraction_service,
        "extract_structured_data",
        lambda document_type, raw_text: {
            "invoice_number": {"value": "123"},
            "subtotal": {"value": 100},
            "tax_amount": {"value": 0},
            "discount": {"value": 0},
            "total_amount": {"value": 100},
            "line_items": [],
        },
    )


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _build_sample_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Invoice #123 total 100")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_process_then_get_document():
    files = {"file": ("invoice_test.pdf", io.BytesIO(_build_sample_pdf_bytes()), "application/pdf")}
    process_response = client.post(
        "/api/v1/documents/process",
        files=files,
        data={"document_type": "invoice"},
    )

    assert process_response.status_code == 200
    body = process_response.json()
    assert body["document_name"] == "invoice_test.pdf"
    assert body["processing_status"] == "completed"

    get_response = client.get("/api/v1/documents/invoice_test.pdf")
    assert get_response.status_code == 200
    assert get_response.json()["document_name"] == "invoice_test.pdf"


def test_get_unknown_document_returns_404():
    response = client.get("/api/v1/documents/does-not-exist.pdf")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"
