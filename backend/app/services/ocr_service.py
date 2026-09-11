import io
from typing import List, Tuple

import fitz
import pytesseract
from PIL import Image, ImageFilter, ImageOps

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

TESSERACT_CONFIG = "--oem 3 --psm 6 -c preserve_interword_spaces=1"
MIN_OCR_DIMENSION = 1800

if settings.tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


def extract_text(content: bytes, extension: str) -> Tuple[str, bool]:
    if extension == "pdf":
        return _extract_from_pdf(content)
    return _extract_from_image(content), True


def _extract_from_pdf(content: bytes) -> Tuple[str, bool]:
    doc = fitz.open(stream=content, filetype="pdf")
    text_by_page: List[str] = []
    native_text_found = False

    for page in doc:
        page_text = page.get_text().strip()
        if page_text:
            native_text_found = True
        text_by_page.append(page_text)

    if native_text_found:
        doc.close()
        return _join_pages(text_by_page), False

    ocr_pages: List[str] = []
    for page in doc:
        pixmap = page.get_pixmap(dpi=300)
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
        processed = _preprocess_for_ocr(image)
        ocr_pages.append(pytesseract.image_to_string(processed, config=TESSERACT_CONFIG))
    doc.close()

    return _join_pages(ocr_pages), True


def _extract_from_image(content: bytes) -> str:
    image = Image.open(io.BytesIO(content))
    processed = _preprocess_for_ocr(image)
    return pytesseract.image_to_string(processed, config=TESSERACT_CONFIG)


def _preprocess_for_ocr(image: Image.Image) -> Image.Image:
    grayscale = image.convert("L")

    width, height = grayscale.size
    longest_side = max(width, height)
    if longest_side < MIN_OCR_DIMENSION:
        scale = MIN_OCR_DIMENSION / longest_side
        grayscale = grayscale.resize(
            (int(width * scale), int(height * scale)), Image.LANCZOS
        )

    contrast_boosted = ImageOps.autocontrast(grayscale, cutoff=1)
    sharpened = contrast_boosted.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    binarized = _binarize(sharpened)

    return binarized


def _otsu_threshold(image: Image.Image) -> int:
    histogram = image.histogram()
    total_pixels = sum(histogram)
    sum_all = sum(level * count for level, count in enumerate(histogram))

    sum_background = 0
    weight_background = 0
    best_threshold = 128
    best_variance = 0.0

    for level in range(256):
        weight_background += histogram[level]
        if weight_background == 0:
            continue

        weight_foreground = total_pixels - weight_background
        if weight_foreground == 0:
            break

        sum_background += level * histogram[level]
        mean_background = sum_background / weight_background
        mean_foreground = (sum_all - sum_background) / weight_foreground

        between_class_variance = (
            weight_background * weight_foreground * (mean_background - mean_foreground) ** 2
        )
        if between_class_variance > best_variance:
            best_variance = between_class_variance
            best_threshold = level

    return best_threshold


def _binarize(image: Image.Image) -> Image.Image:
    threshold = _otsu_threshold(image)
    return image.point(lambda pixel: 255 if pixel > threshold else 0)


def _join_pages(pages: List[str]) -> str:
    labeled = [f"--- PAGE {index + 1} ---\n{text}" for index, text in enumerate(pages)]
    return "\n\n".join(labeled)