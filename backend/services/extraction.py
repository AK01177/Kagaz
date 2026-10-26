import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from storage.document_storage import DocumentStorage

# AI-08: extended to include image formats alongside PDF
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

_WHITESPACE_RUN = re.compile(r"[ \t]+")
_BLANK_LINE_RUN = re.compile(r"\n{3,}")


class ExtractionError(Exception):
    """Raised when a document cannot be processed for text extraction."""


class UnsupportedDocumentTypeError(ExtractionError):
    def __init__(self, extension: str):
        self.extension = extension
        super().__init__(f"Unsupported document type: '{extension}'")


def extract_text(document_id: str, storage: DocumentStorage | None = None) -> str:
    """Load a stored document and return its combined, normalised text.

    Supports text-based PDFs (fast pypdf path), scanned PDFs and images
    (via the OCR service introduced in AI-08).

    Raises DocumentNotFoundError if the document is missing, and
    ExtractionError (or a subclass) if it exists but cannot be processed.
    """
    storage = storage or DocumentStorage()

    path = storage.resolve(document_id)
    suffix = path.suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedDocumentTypeError(suffix)

    # Image files always go through the OCR service
    if suffix in {".png", ".jpg", ".jpeg"}:
        return _extract_via_ocr(path, document_id)

    # PDF: try embedded text first, delegate to OCR for scanned pages
    try:
        reader = PdfReader(str(path))
        pages_text = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, OSError) as exc:
        raise ExtractionError(
            f"Failed to extract text from document '{document_id}': {exc}"
        ) from exc

    combined = "\n".join(pages_text)
    normalised = _normalize_whitespace(combined)

    # Fall back to OCR when the PDF appears to be image-only (no embedded text)
    if not normalised:
        return _extract_via_ocr(path, document_id)

    return normalised


def _extract_via_ocr(path, document_id: str) -> str:
    """Delegate to services.ocr and translate OcrExtractionError."""
    try:
        from services.ocr import OcrExtractionError, extract_text_from_file  # noqa: PLC0415
        return extract_text_from_file(path)
    except Exception as exc:  # OcrExtractionError or ImportError
        raise ExtractionError(
            f"OCR extraction failed for document '{document_id}': {exc}"
        ) from exc


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RUN.sub(" ", text)
    text = _BLANK_LINE_RUN.sub("\n\n", text)
    return text.strip()


# Re-export structured extraction functionality
try:
    from services.structured_extraction import (
        StructuredExtractionError,
        extract_structured_fields,
        parse_and_validate_fields,
    )
except ImportError:
    from backend.services.structured_extraction import (
        StructuredExtractionError,
        extract_structured_fields,
        parse_and_validate_fields,
    )

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "ExtractionError",
    "UnsupportedDocumentTypeError",
    "extract_text",
    "StructuredExtractionError",
    "extract_structured_fields",
    "parse_and_validate_fields",
]


