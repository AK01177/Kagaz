"""
AI-08: OCR and Multi-format Text Extraction
Provides a unified interface for extracting readable text from:
  - Text-based PDFs  (embedded text via pypdf)
  - Scanned/image-only PDFs  (rendered with pdf2image then OCR'd)
  - PNG, JPG, JPEG images  (direct OCR)

The public API is a single function: extract_text_from_file(path).
All OCR is performed through PaddleOCR. Callers (classification service,
structured extraction service) stay unaware of which code path was used.

Graceful degradation
- PaddleOCR and pdf2image are optional at import time.  If they are not
  installed, only text-based PDFs are supported; other formats raise
  UnsupportedDocumentTypeError rather than crashing the process.
- An unreadable or empty result raises OcrExtractionError with a clear
  message so upstream services can mark the document as FAILED / REVIEW.
"""
from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Optional

from pypdf import PdfReader
from pypdf.errors import PdfReadError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy dependencies — imported lazily so the module still loads
# when they are absent (e.g. in CI that only runs text-PDF tests).
# ---------------------------------------------------------------------------
try:
    from paddleocr import PaddleOCR  # type: ignore[import]

    _PADDLE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PADDLE_AVAILABLE = False
    PaddleOCR = None  # type: ignore[assignment,misc]

try:
    from pdf2image import convert_from_path  # type: ignore[import]

    _PDF2IMAGE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PDF2IMAGE_AVAILABLE = False
    convert_from_path = None  # type: ignore[assignment]

# Supported file extensions
TEXT_PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALL_SUPPORTED_EXTENSIONS = TEXT_PDF_EXTENSIONS | IMAGE_EXTENSIONS

_WHITESPACE_RUN = re.compile(r"[ \t]+")
_BLANK_LINE_RUN = re.compile(r"\n{3,}")

# Singleton PaddleOCR instance — initialised once on first use
_ocr_instance: Optional["PaddleOCR"] = None  # type: ignore[type-arg]


class OcrExtractionError(Exception):
    """Raised when a file exists but text cannot be extracted from it."""


class UnsupportedFormatError(OcrExtractionError):
    """Raised when the file extension is not in ALL_SUPPORTED_EXTENSIONS."""

    def __init__(self, extension: str):
        self.extension = extension
        super().__init__(f"Unsupported file format: '{extension}'")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_text_from_file(path: Path) -> str:
    """Extract and normalise readable text from *path*.

    Dispatches to the correct backend based on file extension:
      .pdf  → try embedded text first; fall back to OCR for scanned pages
      .png / .jpg / .jpeg  → direct PaddleOCR

    Returns:
        Normalised plain-text string (may be empty for blank documents).

    Raises:
        UnsupportedFormatError: Extension not in ALL_SUPPORTED_EXTENSIONS.
        OcrExtractionError: File exists but cannot be processed.
    """
    suffix = path.suffix.lower()

    if suffix not in ALL_SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(suffix)

    if suffix == ".pdf":
        return _extract_from_pdf(path)

    # PNG / JPG / JPEG
    return _extract_via_ocr_from_image(path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_from_pdf(path: Path) -> str:
    """Try embedded text extraction; fall back to OCR for scanned PDFs."""
    try:
        reader = PdfReader(str(path))
        pages_text = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, OSError) as exc:
        raise OcrExtractionError(
            f"Cannot read PDF '{path.name}': {exc}"
        ) from exc

    combined = "\n".join(pages_text)
    normalized = _normalize(combined)

    # If meaningful text was extracted, return it immediately
    if normalized:
        logger.debug("Extracted %d chars from text-based PDF '%s'", len(normalized), path.name)
        return normalized

    # Scanned PDF (no embedded text) — try OCR path
    logger.info(
        "PDF '%s' returned empty embedded text; attempting OCR.",
        path.name,
    )
    return _ocr_pdf(path)


def _ocr_pdf(path: Path) -> str:
    """Render PDF pages as images and OCR each page."""
    if not _PDF2IMAGE_AVAILABLE:
        raise OcrExtractionError(
            "pdf2image is not installed. Install it (and poppler) to process scanned PDFs."
        )
    if not _PADDLE_AVAILABLE:
        raise OcrExtractionError(
            "PaddleOCR is not installed. Install paddleocr to process scanned PDFs."
        )

    try:
        with tempfile.TemporaryDirectory(prefix="kagaz_ocr_") as tmp:
            images = convert_from_path(str(path), output_folder=tmp, fmt="png")
            texts = []
            ocr = _get_ocr()
            for img in images:
                import numpy as np  # type: ignore[import]
                arr = np.array(img)
                result = ocr.ocr(arr, cls=True)
                page_lines = _flatten_paddle_result(result)
                texts.append("\n".join(page_lines))
            return _normalize("\n".join(texts))
    except OcrExtractionError:
        raise
    except Exception as exc:
        raise OcrExtractionError(
            f"OCR failed for scanned PDF '{path.name}': {exc}"
        ) from exc


def _extract_via_ocr_from_image(path: Path) -> str:
    """Run PaddleOCR directly on an image file."""
    if not _PADDLE_AVAILABLE:
        raise OcrExtractionError(
            "PaddleOCR is not installed. Install paddleocr to process image files."
        )
    try:
        ocr = _get_ocr()
        result = ocr.ocr(str(path), cls=True)
        lines = _flatten_paddle_result(result)
        text = _normalize("\n".join(lines))
        if not text:
            logger.warning("OCR returned no text for image '%s'.", path.name)
        return text
    except OcrExtractionError:
        raise
    except Exception as exc:
        raise OcrExtractionError(
            f"OCR failed for image '{path.name}': {exc}"
        ) from exc


def _get_ocr() -> "PaddleOCR":  # type: ignore[type-arg]
    """Return the module-level PaddleOCR singleton, initialising it on first call."""
    global _ocr_instance  # noqa: PLW0603
    if _ocr_instance is None:
        logger.info("Initialising PaddleOCR (first use).")
        _ocr_instance = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    return _ocr_instance


def _flatten_paddle_result(result: list | None) -> list[str]:
    """Extract text lines from PaddleOCR's nested result structure.

    PaddleOCR returns a list-of-pages, each page being a list of
    [[box_coords], (text, confidence)] tuples.
    """
    lines: list[str] = []
    if not result:
        return lines
    for page in result:
        if not page:
            continue
        for item in page:
            try:
                # item is [[x1,y1,...], (text, conf)]
                text_conf = item[1]
                text = text_conf[0] if isinstance(text_conf, (list, tuple)) else str(text_conf)
                text = text.strip()
                if text:
                    lines.append(text)
            except (IndexError, TypeError):
                continue
    return lines


def _normalize(text: str) -> str:
    """Normalise whitespace without removing meaningful content."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RUN.sub(" ", text)
    text = _BLANK_LINE_RUN.sub("\n\n", text)
    return text.strip()
