class DocumentIntelligenceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class FileValidationError(DocumentIntelligenceError):
    def __init__(self, message: str):
        super().__init__(code="FILE_VALIDATION_ERROR", message=message, status_code=422)


class ExtractionError(DocumentIntelligenceError):
    def __init__(self, message: str):
        super().__init__(code="EXTRACTION_ERROR", message=message, status_code=502)


class DocumentNotFoundError(DocumentIntelligenceError):
    def __init__(self, document_name: str):
        super().__init__(
            code="DOCUMENT_NOT_FOUND",
            message=f"No processed document found for name '{document_name}'",
            status_code=404,
        )
