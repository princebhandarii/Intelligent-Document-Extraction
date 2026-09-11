import json
from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.document import DocumentRecord


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(
        self,
        document_name: str,
        document_type: str,
        processing_status: str,
        ocr_used: bool,
        processing_time_ms: float,
        response_payload: dict,
    ) -> DocumentRecord:
        record = DocumentRecord(
            document_name=document_name,
            document_type=document_type,
            processing_status=processing_status,
            ocr_used=str(ocr_used).lower(),
            processing_time_ms=processing_time_ms,
            response_json=json.dumps(response_payload, default=str),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_latest_by_name(self, document_name: str) -> Optional[DocumentRecord]:
        return (
            self.db.query(DocumentRecord)
            .filter(DocumentRecord.document_name == document_name)
            .order_by(desc(DocumentRecord.processed_at))
            .first()
        )

    def list_all(self) -> List[DocumentRecord]:
        return self.db.query(DocumentRecord).order_by(desc(DocumentRecord.processed_at)).all()
