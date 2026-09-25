import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi import UploadFile
from pypdf import PdfReader

from storage.document_storage import DocumentStorage


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
CHUNK_BYTES = 64 * 1024
logger = logging.getLogger(__name__)


class UploadError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def save_upload(file: UploadFile, storage: DocumentStorage, user: dict) -> dict:
    """Validate and persist a PDF and its basic metadata without running AI."""
    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not filename or "\x00" in filename:
        raise UploadError(400, "INVALID_FILE", "A valid filename is required.")
    if Path(filename).suffix.lower() != ".pdf" or file.content_type not in {
        "application/pdf", "application/octet-stream", None,
    }:
        raise UploadError(415, "UNSUPPORTED_FILE_TYPE", "Only PDF files are supported.")

    document_id = f"doc_{uuid4().hex}"
    response = {
        "document_id": document_id,
        "filename": filename,
        "file_type": "application/pdf",
        "status": "UPLOADED",
        "uploaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    document_path = storage.base_dir / f"{document_id}.pdf"
    # Keep metadata outside the document glob used by the extraction service.
    metadata_dir = storage.base_dir / "metadata"
    metadata_path = metadata_dir / f"{document_id}.json"
    published_document = False
    try:
        storage.base_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir.mkdir(exist_ok=True)
        with TemporaryDirectory(prefix="upload_", dir=storage.base_dir) as staging:
            staged_document = Path(staging) / "document.pdf"
            size = 0
            with staged_document.open("wb") as destination:
                while chunk := file.file.read(CHUNK_BYTES):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise UploadError(413, "FILE_TOO_LARGE", "Maximum file size is 10 MiB.")
                    destination.write(chunk)
            if size == 0:
                raise UploadError(400, "INVALID_FILE", "The uploaded file is empty.")
            _validate_pdf(staged_document)
            metadata = {
                **response,
                "file_size": size,
                "storage_path": str(document_path.resolve()),
                "submitter_id": user["sub"],
                "organization_id": user["organization_id"],
            }
            staged_metadata = Path(staging) / "metadata.json"
            staged_metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            staged_document.replace(document_path)
            published_document = True
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
