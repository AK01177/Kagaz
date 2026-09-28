import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from storage.document_storage import DocumentStorage

SUPPORTED_EXTENSIONS = {".pdf"}

_WHITESPACE_RUN = re.compile(r"[ \t]+")
_BLANK_LINE_RUN = re.compile(r"\n{3,}")


class ExtractionError(Exception):
    """Raised when a document cannot be processed for text extraction."""


class UnsupportedDocumentTypeError(ExtractionError):
    def __init__(self, extension: str):
        self.extension = extension
        super().__init__(f"Unsupported document type: '{extension}'")


def extract_text(document_id: str, storage: DocumentStorage | None = None) -> str:
    """Load a stored document and return its combined, normalized text.

    Raises DocumentNotFoundError if the document is missing, and
    ExtractionError (or a subclass) if it exists but cannot be processed.
    """
    storage = storage or DocumentStorage()

    path = storage.resolve(document_id)

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise UnsupportedDocumentTypeError(path.suffix)

    try:
        reader = PdfReader(str(path))
        pages_text = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, OSError) as exc:
        raise ExtractionError(f"Failed to extract text from document '{document_id}': {exc}") from exc

    combined = "\n".join(pages_text)
    return _normalize_whitespace(combined)


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RUN.sub(" ", text)
    text = _BLANK_LINE_RUN.sub("\n\n", text)
    return text.strip()
