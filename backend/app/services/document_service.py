import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import (
    DocumentResponse,
    FileValidationResult,
    ProcessingMetadata,
    ProcessingStatus,
)
from app.services import (
    document_validation_service,
    extraction_service,
    financial_validation_service,
    ocr_service,
)
from app.utils.exceptions import DocumentIntelligenceError

logger = get_logger(__name__)


def process_document(db: Session, filename: str, document_type: str, content: bytes) -> DocumentResponse:
    started_at = time.perf_counter()
    document_name = filename
    repository = DocumentRepository(db)

    file_validation = document_validation_service.validate_upload(filename, content)

    raw_text, ocr_used = ocr_service.extract_text(content, file_validation.file_type)
    if not raw_text.strip():
        raise DocumentIntelligenceError(
            code="NO_EXTRACTABLE_TEXT",
            message="No readable text could be found in the document",
            status_code=422,
        )

    extracted_data = extraction_service.extract_structured_data(document_type, raw_text)
    validation_summary = financial_validation_service.run_validation(document_type, extracted_data)

    processing_time_ms = round((time.perf_counter() - started_at) * 1000, 2)
    processed_at = datetime.now(timezone.utc)

    response = DocumentResponse(
        document_name=document_name,
        document_type=document_type,
        processing_status=ProcessingStatus.completed,
        file_validation=file_validation,
        extracted_data=extracted_data,
        validation=validation_summary,
        processing_metadata=ProcessingMetadata(
            ocr_used=ocr_used,
            processed_at=processed_at,
            processing_time_ms=processing_time_ms,
        ),
    )

    repository.save(
        document_name=document_name,
        document_type=document_type,
        processing_status=ProcessingStatus.completed.value,
        ocr_used=ocr_used,
        processing_time_ms=processing_time_ms,
        response_payload=response.model_dump(mode="json"),
    )

    return response


def get_document_by_name(db: Session, document_name: str) -> dict:
    from app.utils.exceptions import DocumentNotFoundError

    repository = DocumentRepository(db)
    record = repository.get_latest_by_name(document_name)
    if not record:
        raise DocumentNotFoundError(document_name)

    import json

    return json.loads(record.response_json)


def list_documents(db: Session) -> list:
    repository = DocumentRepository(db)
    records = repository.list_all()
    return [
        {
            "document_name": record.document_name,
            "document_type": record.document_type,
            "processing_status": record.processing_status,
            "processed_at": record.processed_at,
        }
        for record in records
    ]
