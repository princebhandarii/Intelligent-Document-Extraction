from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class DocumentType(str, Enum):
    invoice = "invoice"
    balance_sheet = "balance_sheet"
    profit_and_loss = "profit_and_loss"
    cash_flow_statement = "cash_flow_statement"


class ProcessingStatus(str, Enum):
    completed = "completed"
    failed = "failed"


class ValidationStatus(str, Enum):
    pass_ = "PASS"
    fail = "FAIL"
    not_applicable = "NOT_APPLICABLE"


class FileValidationResult(BaseModel):
    is_valid: bool
    file_type: Optional[str] = None
    page_count: Optional[int] = None
    errors: List[str] = []


class ValidationCheck(BaseModel):
    name: str
    formula: str
    operands: dict
    calculated_value: Optional[float] = None
    reported_value: Optional[float] = None
    variance: Optional[float] = None
    status: ValidationStatus
    period_label: Optional[str] = None


class ValidationSummary(BaseModel):
    checks: List[ValidationCheck] = []
    overall_status: ValidationStatus


class ProcessingMetadata(BaseModel):
    ocr_used: bool
    processed_at: datetime
    processing_time_ms: float


class DocumentResponse(BaseModel):
    document_name: str
    document_type: DocumentType
    processing_status: ProcessingStatus
    file_validation: FileValidationResult
    extracted_data: dict
    validation: ValidationSummary
    processing_metadata: ProcessingMetadata


class DocumentListItem(BaseModel):
    document_name: str
    document_type: str
    processing_status: str
    processed_at: datetime


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
