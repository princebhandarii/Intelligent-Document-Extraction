import uuid

from sqlalchemy import Column, DateTime, Float, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class DocumentRecord(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_name = Column(String, index=True, nullable=False)
    document_type = Column(String, nullable=False)
    processing_status = Column(String, nullable=False)
    ocr_used = Column(String, nullable=False, default="false")
    processing_time_ms = Column(Float, nullable=False, default=0.0)
    response_json = Column(Text, nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
