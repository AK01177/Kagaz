import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi import UploadFile
from pypdf import PdfReader

from storage.document_storage import DocumentStorage


from services.extraction import extract_text, ExtractionError
from services.classification import classify_document, ClassificationError
from services.structured_extraction import (
    StructuredExtractionError,
    UnsupportedDocumentTypeError,
    extract_structured_fields,
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
CHUNK_BYTES = 64 * 1024
logger = logging.getLogger(__name__)


def _legacy_json_enabled() -> bool:
    """Return True when KAGAZ_LEGACY_JSON_FALLBACK=1 is set.

    When enabled, the upload service writes a JSON sidecar alongside the binary
    file for backward compatibility with pre-DB-03 test fixtures.
    In production this MUST NOT be set; PostgreSQL is the authoritative store.
    """
    return os.getenv("KAGAZ_LEGACY_JSON_FALLBACK", "").strip() == "1"

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


def save_upload(file: UploadFile, storage: DocumentStorage, user: dict, db: any = None) -> dict:
    """Validate and persist a PDF or image file, extract text, classify and field-extract it.

    BE-07: Accepts PDF, PNG, JPG and JPEG.  Validates by extension and,
    where practical, by magic bytes / PDF header.  The canonical MIME type
    is derived from the extension and stored in metadata regardless of what
    the client sent.

    Sprint 2: After classification, automatically runs structured field
    extraction and persists fields + confidence into PostgreSQL via
    app.crud.extraction (DB-03). When KAGAZ_LEGACY_JSON_FALLBACK=1 is set,
    also writes a JSON sidecar for backward compatibility.
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

            doc = None
            if db is not None:
                try:
                    from app.crud.document import create_document
                    from app.models.document import DocumentStatus

                    doc = create_document(
                        db,
                        id=document_id,
                        organization_id=user.get("organization_id", "dev_org"),
                        uploaded_by=user.get("sub", "dev_user"),
                        filename=filename,
                        file_type=canonical_mime,
                        file_size=size,
                        storage_path=str(document_path.resolve()),
                        status=DocumentStatus.UPLOADED,
                    )
                except Exception as db_exc:
                    if published_document:
                        try:
                            document_path.unlink(missing_ok=True)
                        except OSError:
                            pass
                    logger.exception("Failed to persist initial document record to DB for %s", document_id)
                    raise UploadError(500, "STORAGE_FAILURE", "Failed to persist document metadata.") from db_exc

            extracted_fields = None
            extracted_confidences = None
            ocr_text: str = ""

            try:
                # Step 1: OCR / text extraction
                ocr_text = extract_text(document_id, storage)
                logger.info("OCR complete for %s: %d chars", document_id, len(ocr_text))

                # Step 2: Classification
                classification = classify_document(ocr_text)
                response["category"] = classification.category.value
                response["confidence"] = classification.confidence
                response["status"] = "CLASSIFIED"
                logger.info(
                    "Classified %s as '%s' (confidence=%.2f)",
                    document_id,
                    classification.category.value,
                    classification.confidence,
                )

                if db is not None and doc is not None:
                    from app.models.document import DocumentStatus
                    doc.classification = classification.category.value
                    doc.classification_confidence = classification.confidence
                    doc.status = DocumentStatus.CLASSIFIED
                    doc.processed_at = datetime.now(timezone.utc)
                    db.commit()
                    db.refresh(doc)

                # Step 3: Structured field extraction (Sprint 2)
                try:
                    extraction = extract_structured_fields(ocr_text, classification.category.value)
                    raw_fields = extraction.to_flat_dict()
                    raw_conf = extraction.get_field_confidences()
                    non_none_fields = {k: v for k, v in raw_fields.items() if v is not None}
                    if non_none_fields:
                        extracted_fields = non_none_fields
                        extracted_confidences = {k: v for k, v in raw_conf.items() if k in non_none_fields}
                        response["status"] = "EXTRACTED"
                        logger.info(
                            "Field extraction complete for %s: %d field(s) found",
                            document_id,
                            len(extracted_fields),
                        )
                    else:
                        extracted_fields = None
                        extracted_confidences = None

                    if db is not None and doc is not None:
                        try:
                            from services.extraction_persistence import persist_extraction_result
                            from app.models.document import DocumentStatus
                            persist_extraction_result(
                                db,
                                document_id,
                                extraction,
                                document_type=classification.category.value,
                            )
                            doc.status = DocumentStatus.EXTRACTED
                            doc.processed_at = datetime.now(timezone.utc)
                            db.commit()
                            db.refresh(doc)
                        except Exception as p_err:
                            logger.exception("Failed to persist extraction to db for %s: %s", document_id, p_err)
                            response["status"] = "CLASSIFIED"
                            doc.status = DocumentStatus.CLASSIFIED
                            db.commit()
                            extracted_fields = None
                            extracted_confidences = None
                except (StructuredExtractionError, UnsupportedDocumentTypeError) as exc:
                    logger.info("Structured extraction skipped or failed for document %s: %s", document_id, exc)
                    if db is not None and doc is not None:
                        try:
                            from services.extraction_persistence import record_failed_extraction_run
                            record_failed_extraction_run(
                                db,
                                document_id,
                                document_type=classification.category.value,
                                error_message=str(exc),
                            )
                        except Exception:
                            pass
                except Exception as ex_err:
                    logger.warning("Structured extraction failed for %s (non-fatal): %s", document_id, ex_err)
                    if db is not None and doc is not None:
                        try:
                            from services.extraction_persistence import record_failed_extraction_run
                            record_failed_extraction_run(
                                db,
                                document_id,
                                document_type=classification.category.value,
                                error_message=str(ex_err),
                            )
                        except Exception:
                            pass

            except (ExtractionError, ClassificationError) as e:
                logger.exception("Failed to classify document %s", document_id)
                response["category"] = "unknown"
                response["confidence"] = 0.0
                if db is not None and doc is not None:
                    doc.classification = "unknown"
                    doc.classification_confidence = 0.0
                    db.commit()

            response["file_size"] = size

            # Write JSON sidecar only when legacy compatibility mode is active.
            # In production (KAGAZ_LEGACY_JSON_FALLBACK not set) PostgreSQL is
            # the sole authoritative store; no sidecar is written.
            if _legacy_json_enabled():
                metadata = {
                    **response,
                    "file_size": size,
                    "storage_path": str(document_path.resolve()),
                    "submitter_id": user["sub"],
                    "organization_id": user["organization_id"],
                    "ocr_text_length": len(ocr_text),
                }
                if extracted_fields is not None:
                    metadata["extracted_fields"] = extracted_fields
                    metadata["extracted_confidence"] = extracted_confidences
                    metadata["status"] = "EXTRACTED"
                staged_metadata = Path(staging) / "metadata.json"
                staged_metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
                staged_metadata.replace(metadata_path)

    except OSError as exc:
        if published_document:
            try:
                document_path.unlink(missing_ok=True)
                metadata_path.unlink(missing_ok=True)  # no-op if sidecar was never written
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
