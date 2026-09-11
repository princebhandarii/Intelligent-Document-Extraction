import pytest

from app.services.document_validation_service import validate_upload
from app.utils.exceptions import FileValidationError


def test_rejects_empty_file():
    with pytest.raises(FileValidationError):
        validate_upload("invoice.pdf", b"")


def test_rejects_unsupported_extension():
    with pytest.raises(FileValidationError):
        validate_upload("invoice.docx", b"some bytes")


def test_rejects_corrupted_pdf():
    with pytest.raises(FileValidationError):
        validate_upload("invoice.pdf", b"not a real pdf")


def test_rejects_corrupted_image():
    with pytest.raises(FileValidationError):
        validate_upload("invoice.png", b"not a real png")
