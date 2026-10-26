import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi import UploadFile
from pypdf import PdfReader

from storage.document_storage import DocumentStorage


from services.extraction import extract_text, ExtractionError
from services.classification import classify_document, ClassificationError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
CHUNK_BYTES = 64 * 1024
logger = logging.getLogger(__name__)

# BE-07: Supported upload formats
# Maps normalised lowercase extension -> canonical MIME type stored in metadata
SUPPORTED_MIME_BY_EXT: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
# Content-types that browsers/clients may send for any binary upload
_AMBIGUOUS_CONTENT_TYPES = {"application/octet-stream", None}
# Magic-byte signatures for image formats
_IMAGE_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"\xff\xd8\xff", "JPEG"),
]


class UploadError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def save_upload(file: UploadFile, storage: DocumentStorage, user: dict) -> dict:
    """Validate and persist a PDF or image file, extract text, and classify it.

    BE-07: Accepts PDF, PNG, JPG and JPEG.  Validates by extension and,
    where practical, by magic bytes / PDF header.  The canonical MIME type
    is derived from the extension and stored in metadata regardless of what
    the client sent.
    """
    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not filename or "\x00" in filename:
        raise UploadError(400, "INVALID_FILE", "A valid filename is required.")

    ext = Path(filename).suffix.lower()
    canonical_mime = SUPPORTED_MIME_BY_EXT.get(ext)
    if canonical_mime is None:
        raise UploadError(
            415,
            "UNSUPPORTED_FILE_TYPE",
            "Only PDF, PNG, JPG and JPEG files are supported.",
        )

    # If the client provides an explicit non-ambiguous content-type, check
    # that it is consistent with the file extension.
    client_ct = (file.content_type or "").lower().split(";")[0].strip()
    if client_ct and client_ct not in _AMBIGUOUS_CONTENT_TYPES:
        allowed_cts = {canonical_mime, "application/octet-stream"}
        if client_ct not in allowed_cts:
            raise UploadError(
                415,
                "UNSUPPORTED_FILE_TYPE",
                "Only PDF, PNG, JPG and JPEG files are supported.",
            )

    document_id = f"doc_{uuid4().hex}"
    response = {
        "document_id": document_id,
        "filename": filename,
        "file_type": canonical_mime,
        "status": "UPLOADED",
        "uploaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    # Store with the correct extension derived from the upload filename
    document_path = storage.base_dir / f"{document_id}{ext}"
    # Keep metadata outside the document glob used by the extraction service.
    metadata_dir = storage.base_dir / "metadata"
    metadata_path = metadata_dir / f"{document_id}.json"
    published_document = False
    try:
        storage.base_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir.mkdir(exist_ok=True)
        with TemporaryDirectory(prefix="upload_", dir=storage.base_dir) as staging:
            staged_document = Path(staging) / f"document{ext}"
            size = 0
            with staged_document.open("wb") as destination:
                while chunk := file.file.read(CHUNK_BYTES):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise UploadError(413, "FILE_TOO_LARGE", "Maximum file size is 10 MiB.")
                    destination.write(chunk)
            if size == 0:
                raise UploadError(400, "INVALID_FILE", "The uploaded file is empty.")

            # Validate file contents by format
            if ext == ".pdf":
                _validate_pdf(staged_document)
            else:
                _validate_image(staged_document, ext)

            staged_document.replace(document_path)
            published_document = True

            try:
                text = extract_text(document_id, storage)
                classification = classify_document(text)
                
                response["category"] = classification.category.value
                response["confidence"] = classification.confidence
                response["status"] = "CLASSIFIED"
            except (ExtractionError, ClassificationError) as e:
                logger.exception("Failed to classify document %s", document_id)
                response["category"] = "unknown"
                response["confidence"] = 0.0
            response["file_size"] = size

            metadata = {
                **response,
                "file_size": size,
                "storage_path": str(document_path.resolve()),
                "submitter_id": user["sub"],
                "organization_id": user["organization_id"],
            }
            staged_metadata = Path(staging) / "metadata.json"
            staged_metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            staged_metadata.replace(metadata_path)
    except OSError as exc:
        if published_document:
            try:
                document_path.unlink(missing_ok=True)
                metadata_path.unlink(missing_ok=True)
            except OSError:
                logger.exception("Could not clean up failed upload %s", document_id)
        logger.exception("Failed to store upload %s", document_id)
        raise UploadError(500, "STORAGE_FAILURE", "The document could not be stored.") from exc
    return response


def _validate_pdf(path: Path) -> None:
    try:
        with path.open("rb") as source:
            if source.read(5) != b"%PDF-":
                raise ValueError("Missing PDF header")
            source.seek(0)
            reader = PdfReader(source)
            if reader.is_encrypted or len(reader.pages) == 0:
                raise ValueError("Encrypted or empty PDF")
    except OSError:
        raise
    except Exception as exc:
        raise UploadError(400, "INVALID_FILE", "Provide a readable, unencrypted PDF with at least one page.") from exc


def _validate_image(path: Path, ext: str) -> None:
    """Check magic bytes to confirm the file is actually a PNG or JPEG."""
    try:
        with path.open("rb") as f:
            header = f.read(16)
    except OSError:
        raise

    for magic, label in _IMAGE_SIGNATURES:
        if header.startswith(magic):
            return  # magic bytes match — file is valid

    raise UploadError(
        400,
        "INVALID_FILE",
        f"The uploaded file does not appear to be a valid {ext.lstrip('.').upper()} image.",
    )
