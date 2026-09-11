import io

import fitz
from PIL import Image

from app.core.config import get_settings
from app.schemas.document import FileValidationResult
from app.utils.exceptions import FileValidationError

settings = get_settings()

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}


def validate_upload(filename: str, content: bytes) -> FileValidationResult:
    errors = []

    if not content:
        raise FileValidationError("Uploaded file is empty")

    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise FileValidationError(
            f"File exceeds maximum allowed size of {settings.max_upload_size_mb}MB"
        )

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Unsupported file type '.{extension}'. Allowed types: pdf, jpg, jpeg, png"
        )

    page_count = 1
    if extension == "pdf":
        page_count = _validate_pdf(content)
    else:
        _validate_image(content)

    if page_count > settings.max_upload_pages:
        raise FileValidationError(
            f"Document has {page_count} pages, which exceeds the limit of "
            f"{settings.max_upload_pages} pages"
        )

    return FileValidationResult(
        is_valid=True,
        file_type=extension,
        page_count=page_count,
        errors=errors,
    )


def _validate_pdf(content: bytes) -> int:
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        page_count = doc.page_count
        doc.close()
    except Exception as exc:
        raise FileValidationError("Uploaded PDF is corrupted or unreadable") from exc

    if page_count == 0:
        raise FileValidationError("Uploaded PDF contains no pages")

    return page_count


def _validate_image(content: bytes) -> None:
    try:
        image = Image.open(io.BytesIO(content))
        image.verify()
    except Exception as exc:
        raise FileValidationError("Uploaded image is corrupted or unreadable") from exc
