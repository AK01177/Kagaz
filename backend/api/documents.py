"""
Document API endpoints.

DB-03: PostgreSQL Document and Extraction Persistence Integration
- PostgreSQL is the authoritative source for all document metadata and extractions.
- Multi-tenant boundary enforcement via organization_id.
- Extraction runs tracked hierarchically: Document -> Extraction Run -> Extracted Fields.
- File binaries remain in object storage (never in PostgreSQL).

Legacy JSON Compatibility (DEPRECATED):
- Enabled only when the KAGAZ_LEGACY_JSON_FALLBACK=1 environment variable is set.
- When enabled, the API checks storage_data/metadata/{id}.json as a fallback for
  unmigrated demo documents that do not yet exist in PostgreSQL.
- In production (default), legacy JSON fallback is DISABLED: a missing PostgreSQL
  record produces 404, not a silent JSON read. Use the migrate_json_metadata.py script
  to import demo records into PostgreSQL first.
- JSON sidecar writes are also conditional on this flag and are retained only for
  backward compatibility with pre-DB-03 test fixtures and development workflows.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from api.auth import require_reviewer, require_submitter
from api.upload_limit import UploadLimitRoute
try:
    from app.db.session import get_db
except ImportError:
    from backend.app.db.session import get_db

try:
    from app.models.document import Document, DocumentStatus, utc_now
    from app.models.extraction import Extraction, ExtractionRun, ExtractionStatus
    from app.crud.extraction import (
        create_extraction_run,
        get_extractions_by_document,
        get_latest_extraction_run,
    )
    from app.crud.document import list_documents_by_organization
except ImportError:
    from backend.app.models.document import Document, DocumentStatus, utc_now
    from backend.app.models.extraction import Extraction, ExtractionRun, ExtractionStatus
    from backend.app.crud.extraction import (
        create_extraction_run,
        get_extractions_by_document,
        get_latest_extraction_run,
    )
    from backend.app.crud.document import list_documents_by_organization

from services.classification import ClassificationError, DocumentCategory, classify_document
from services.extraction import ExtractionError, extract_text
from services.extraction_persistence import persist_extraction_result, record_failed_extraction_run
from services.structured_extraction import (
    StructuredExtractionError,
    UnsupportedDocumentTypeError,
    extract_structured_fields,
)
from services.upload import UploadError, save_upload
from storage.document_storage import DocumentNotFoundError, DocumentStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"], route_class=UploadLimitRoute)


def _legacy_fallback_enabled() -> bool:
    """Return True only when KAGAZ_LEGACY_JSON_FALLBACK=1 is explicitly set.

    In production this variable MUST NOT be set. It exists only to support
    development workflows that have not yet run the JSON->PostgreSQL migration
    (backend/scripts/migrate_json_metadata.py).
    """
    return os.getenv("KAGAZ_LEGACY_JSON_FALLBACK", "").strip() == "1"


class ClassificationCorrectionRequest(BaseModel):
    category: str = Field(..., description="The corrected document category.")
    notes: Optional[str] = Field(None, description="Optional reviewer notes or rationale for correction.")


# ---------------------------------------------------------------------------
# POST /api/documents — upload a document
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def upload_document(
    user: Annotated[dict, Depends(require_submitter)],
    file: Annotated[UploadFile | None, File()] = None,
    db: Session = Depends(get_db),
):
    try:
        if file is None:
            raise UploadError(400, "INVALID_FILE", "A file is required.")
        return await run_in_threadpool(save_upload, file, DocumentStorage(), user, db)
    except UploadError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )
    finally:
        if file is not None:
            await file.close()


# ---------------------------------------------------------------------------
# GET /api/documents — list documents for caller's organization
# ---------------------------------------------------------------------------

@router.get("")
async def list_documents(
    user: Annotated[dict, Depends(require_submitter)],
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    """List documents for the authenticated organization from PostgreSQL."""
    org_id = user.get("organization_id", "dev_org")
    docs = list_documents_by_organization(db, org_id, skip=skip, limit=limit)
    return [
        {
            "document_id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "status": d.status.value,
            "uploaded_at": d.upload_timestamp.isoformat().replace("+00:00", "Z"),
            "category": d.classification,
            "confidence": d.classification_confidence,
        }
        for d in docs
    ]


# ---------------------------------------------------------------------------
# GET /api/documents/{document_id}/file — download raw document binary
# ---------------------------------------------------------------------------

@router.get("/{document_id}/file")
async def get_document_file(document_id: str):
    storage = DocumentStorage()
    try:
        file_path = storage.resolve(document_id)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document file not found")

    ext = file_path.suffix.lower()
    media_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    media_type = media_types.get(ext, "application/octet-stream")
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
        headers={"Content-Disposition": f'inline; filename="{file_path.name}"'},
    )


# ---------------------------------------------------------------------------
# GET /api/documents/{document_id} — fetch document metadata
# ---------------------------------------------------------------------------

@router.get("/{document_id}")
async def get_document(
    document_id: str,
    user: Annotated[dict, Depends(require_submitter)],
    db: Session = Depends(get_db),
):
    # --- 1. Authoritative lookup in PostgreSQL ---
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is not None:
        user_org = user.get("organization_id")
        if user_org and doc.organization_id != user_org:
            raise HTTPException(status_code=403, detail="Access denied for this document's organization.")

        extractions = (
            db.query(Extraction)
            .filter(Extraction.document_id == document_id)
            .order_by(Extraction.field_name.asc())
            .all()
        )
        fields = {e.field_name: e.value for e in extractions} if extractions else None
        confidence = {e.field_name: e.confidence for e in extractions} if extractions else None

        result = {
            "document_id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "storage_path": doc.storage_path,
            "status": doc.status.value,
            "uploaded_at": doc.upload_timestamp.isoformat().replace("+00:00", "Z"),
            "submitter_id": doc.uploaded_by,
            "organization_id": doc.organization_id,
            "category": doc.classification,
            "confidence": doc.classification_confidence,
        }
        if doc.processed_at:
            result["processed_at"] = doc.processed_at.isoformat().replace("+00:00", "Z")
        if fields is not None:
            result["extracted_fields"] = fields
            result["extracted_confidence"] = confidence
        return result

    # --- 2. Legacy JSON fallback (ONLY when KAGAZ_LEGACY_JSON_FALLBACK=1) ---
    if not _legacy_fallback_enabled():
        raise HTTPException(status_code=404, detail="Document not found")

    logger.warning(
        "Document %s not in PostgreSQL; falling back to JSON sidecar (KAGAZ_LEGACY_JSON_FALLBACK=1). "
        "Run migrate_json_metadata.py to import this record.",
        document_id,
    )
    storage = DocumentStorage()
    metadata_path = storage.base_dir / "metadata" / f"{document_id}.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not read metadata")

    user_org = user.get("organization_id")
    if user_org and metadata.get("organization_id") and metadata.get("organization_id") != user_org:
        raise HTTPException(status_code=403, detail="Access denied for this document's organization.")

    return metadata


# ---------------------------------------------------------------------------
# PATCH /api/documents/{document_id}/classification — correct classification
# ---------------------------------------------------------------------------

@router.patch("/{document_id}/classification")
async def correct_classification(
    document_id: str,
    payload: ClassificationCorrectionRequest,
    user: Annotated[dict, Depends(require_reviewer)],
    db: Session = Depends(get_db),
):
    storage = DocumentStorage()
    doc = db.query(Document).filter(Document.id == document_id).first()
    metadata_path = storage.base_dir / "metadata" / f"{document_id}.json"

    # Document must exist in PostgreSQL or (if legacy fallback enabled) in JSON sidecar
    if doc is None:
        if not _legacy_fallback_enabled() or not metadata_path.exists():
            raise HTTPException(status_code=404, detail="Document not found")

    if doc is not None:
        user_org = user.get("organization_id")
        if user_org and doc.organization_id != user_org:
            raise HTTPException(status_code=403, detail="Access denied for this document's organization.")

    valid_categories = [c.value for c in DocumentCategory]
    normalized_category = payload.category.strip().lower()
    if normalized_category not in valid_categories:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid category '{payload.category}'. Valid categories are: {', '.join(valid_categories)}",
        )

    # Re-run text extraction & field extraction for the corrected category
    extracted_fields = None
    extracted_conf = None
    extraction_obj = None
    try:
        text = extract_text(document_id, storage)
        extraction_obj = extract_structured_fields(text, normalized_category)
        raw_fields = extraction_obj.to_flat_dict()
        raw_conf = extraction_obj.get_field_confidences()
        extracted_fields = {k: v for k, v in raw_fields.items() if v is not None}
        extracted_conf = {k: v for k, v in raw_conf.items() if k in extracted_fields}
    except Exception:
        pass

    # 1. Update PostgreSQL (authoritative)
    if doc is not None:
        doc.classification = normalized_category
        doc.classification_confidence = 1.0
        doc.processed_at = utc_now()
        if extracted_fields and extraction_obj is not None:
            run = create_extraction_run(
                db,
                document_id=doc.id,
                status=ExtractionStatus.SUCCESS,
                document_type=normalized_category,
            )
            persist_extraction_result(
                db,
                doc.id,
                extraction_obj,
                extraction_run_id=run.id,
                document_type=normalized_category,
            )
            doc.status = DocumentStatus.EXTRACTED
        else:
            doc.status = DocumentStatus.CLASSIFIED
        db.commit()
        db.refresh(doc)

    # 2. Update JSON sidecar (only when legacy compatibility mode is active)
    history = []
    if _legacy_fallback_enabled():
        metadata = {}
        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception:
                pass

        history = metadata.get("classification_history", [])
        history.append({
            "previous_category": metadata.get("category"),
            "previous_confidence": metadata.get("confidence"),
            "updated_category": normalized_category,
            "corrected_at": utc_now().isoformat().replace("+00:00", "Z"),
            "notes": payload.notes,
            "corrected_by": user.get("sub", "reviewer"),
        })
        metadata["category"] = normalized_category
        metadata["confidence"] = 1.0
        metadata["is_manually_corrected"] = True
        metadata["last_corrected_at"] = utc_now().isoformat().replace("+00:00", "Z")
        metadata["classification_history"] = history

        if extracted_fields:
            metadata["extracted_fields"] = extracted_fields
            metadata["extracted_confidence"] = extracted_conf
            metadata["status"] = "EXTRACTED"
        else:
            metadata.pop("extracted_fields", None)
            metadata.pop("extracted_confidence", None)
            metadata["status"] = "CLASSIFIED"

        if metadata_path.parent.is_dir():
            try:
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2)
            except Exception:
                pass

    if doc is not None:
        extractions = (
            db.query(Extraction)
            .filter(Extraction.document_id == document_id)
            .order_by(Extraction.field_name.asc())
            .all()
        )
        fields = {e.field_name: e.value for e in extractions} if extractions else None
        db_confidence = {e.field_name: e.confidence for e in extractions} if extractions else None
        return {
            "document_id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "storage_path": doc.storage_path,
            "status": doc.status.value,
            "uploaded_at": doc.upload_timestamp.isoformat().replace("+00:00", "Z"),
            "submitter_id": doc.uploaded_by,
            "organization_id": doc.organization_id,
            "category": doc.classification,
            "confidence": doc.classification_confidence,
            "extracted_fields": fields,
            "extracted_confidence": db_confidence,
            "classification_history": history,
            "is_manually_corrected": True,
            "last_corrected_at": utc_now().isoformat().replace("+00:00", "Z"),
        }

    # Legacy-only path: document is only in JSON sidecar
    if _legacy_fallback_enabled():
        return metadata  # type: ignore[return-value]

    raise HTTPException(status_code=404, detail="Document not found")


# ---------------------------------------------------------------------------
# GET /api/documents/{document_id}/extract — extraction results
# ---------------------------------------------------------------------------

@router.get("/{document_id}/extract")
async def get_extraction_results(
    document_id: str,
    user: Annotated[dict, Depends(require_reviewer)],
    db: Session = Depends(get_db),
):
    storage = DocumentStorage()
    doc = db.query(Document).filter(Document.id == document_id).first()

    if doc is not None:
        user_org = user.get("organization_id")
        if user_org and doc.organization_id != user_org:
            raise HTTPException(status_code=403, detail="Access denied for this document's organization.")

        extractions = (
            db.query(Extraction)
            .filter(Extraction.document_id == document_id)
            .order_by(Extraction.field_name.asc())
            .all()
        )
        fields = {r.field_name: r.value for r in extractions}
        confidence = {r.field_name: r.confidence for r in extractions}

        # PostgreSQL is authoritative: empty extractions means no extractions yet.
        # We do NOT fall back to JSON even if legacy mode is enabled, to avoid
        # stale JSON data silently masking missing DB records.
        status = "EXTRACTED" if fields else doc.status.value
        return {
            "document_id": doc.id,
            "document_type": doc.classification,
            "fields": fields,
            "confidence": confidence,
            "status": status,
        }

    # Document not in PostgreSQL
    if not _legacy_fallback_enabled():
        raise HTTPException(status_code=404, detail="Document not found")

    # Legacy fallback for unmigrated demo documents
    logger.warning(
        "Document %s not in PostgreSQL; serving extractions from JSON sidecar "
        "(KAGAZ_LEGACY_JSON_FALLBACK=1). Run migrate_json_metadata.py.",
        document_id,
    )
    metadata_path = storage.base_dir / "metadata" / f"{document_id}.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not read metadata")

    user_org = user.get("organization_id")
    if user_org and metadata.get("organization_id") and metadata.get("organization_id") != user_org:
        raise HTTPException(status_code=403, detail="Access denied for this document's organization.")

    fields: dict = metadata.get("extracted_fields", {})
    confidence: dict = metadata.get("extracted_confidence", {})
    extraction_status = "EXTRACTED" if fields else metadata.get("status", "UPLOADED")

    return {
        "document_id": document_id,
        "document_type": metadata.get("category"),
        "fields": fields,
        "confidence": confidence,
        "status": extraction_status,
    }


# ---------------------------------------------------------------------------
# POST /api/documents/{document_id}/extract — re-run structured extraction
# ---------------------------------------------------------------------------

@router.post("/{document_id}/extract")
async def run_extraction(
    document_id: str,
    user: Annotated[dict, Depends(require_reviewer)],
    db: Session = Depends(get_db),
):
    storage = DocumentStorage()
    doc = db.query(Document).filter(Document.id == document_id).first()
    metadata_path = storage.base_dir / "metadata" / f"{document_id}.json"

    # Must exist in PostgreSQL or (if legacy enabled) in JSON sidecar
    if doc is None:
        if not _legacy_fallback_enabled() or not metadata_path.exists():
            raise HTTPException(status_code=404, detail="Document not found")

    if doc is not None:
        user_org = user.get("organization_id")
        if user_org and doc.organization_id != user_org:
            raise HTTPException(status_code=403, detail="Access denied for this document's organization.")
        document_category = doc.classification
    else:
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            document_category = metadata.get("category")
        except Exception:
            raise HTTPException(status_code=500, detail="Could not read metadata")

    try:
        text = await run_in_threadpool(extract_text, document_id, storage)
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=f"Text extraction failed: {exc}")

    if not document_category or document_category == "unknown":
        try:
            classification = await run_in_threadpool(classify_document, text)
            document_category = classification.category.value
            if doc is not None:
                doc.classification = document_category
                doc.classification_confidence = classification.confidence
                doc.status = DocumentStatus.CLASSIFIED
                db.commit()
        except Exception:
            raise HTTPException(
                status_code=422,
                detail="Document must be classified before extraction can run.",
            )

    try:
        extraction_result = await run_in_threadpool(
            extract_structured_fields, text, document_category
        )
        raw_fields = extraction_result.to_flat_dict()
        raw_conf = extraction_result.get_field_confidences()
        extracted_fields = {k: v for k, v in raw_fields.items() if v is not None}
        extracted_confidence = {k: v for k, v in raw_conf.items() if k in extracted_fields}
    except Exception as exc:
        if doc is not None:
            record_failed_extraction_run(
                db,
                document_id=doc.id,
                document_type=document_category,
                error_message=str(exc),
            )
        raise HTTPException(status_code=422, detail=f"Structured extraction failed: {exc}")

    # 1. Update PostgreSQL (authoritative)
    if doc is not None:
        run = create_extraction_run(
            db,
            document_id=doc.id,
            status=ExtractionStatus.SUCCESS,
            document_type=document_category,
        )
        persist_extraction_result(
            db,
            doc.id,
            extraction_result,
            extraction_run_id=run.id,
            document_type=document_category,
        )
        doc.status = DocumentStatus.EXTRACTED
        doc.processed_at = utc_now()
        db.commit()
        db.refresh(doc)

    # 2. Update JSON sidecar (only when legacy compatibility mode is active)
    if _legacy_fallback_enabled() and metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta["category"] = document_category
            meta["extracted_fields"] = extracted_fields
            meta["extracted_confidence"] = extracted_confidence
            meta["status"] = "EXTRACTED"
            meta["ocr_text_length"] = len(text)
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception:
            pass

    return {
        "document_id": document_id,
        "document_type": document_category,
        "fields": extracted_fields,
        "confidence": extracted_confidence,
        "status": "EXTRACTED",
        "ocr_text_length": len(text),
    }


# ---------------------------------------------------------------------------
# POST /api/documents/{document_id}/classify — re-run classification
# ---------------------------------------------------------------------------

@router.post("/{document_id}/classify")
async def reclassify_document(
    document_id: str,
    user: Annotated[dict, Depends(require_submitter)],
    db: Session = Depends(get_db),
):
    storage = DocumentStorage()
    doc = db.query(Document).filter(Document.id == document_id).first()
    metadata_path = storage.base_dir / "metadata" / f"{document_id}.json"

    # Must exist in PostgreSQL or (if legacy enabled) in JSON sidecar
    if doc is None:
        if not _legacy_fallback_enabled() or not metadata_path.exists():
            raise HTTPException(status_code=404, detail="Document not found")

    if doc is not None:
        user_org = user.get("organization_id")
        if user_org and doc.organization_id != user_org:
            raise HTTPException(status_code=403, detail="Access denied for this document's organization.")

    # Read JSON sidecar only when legacy mode is active
    metadata = {}
    if _legacy_fallback_enabled() and metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            pass

    try:
        text = extract_text(document_id, storage)
        result = classify_document(text)
        new_category = result.category.value
        new_confidence = result.confidence

        extracted_fields = None
        extracted_confidences = None
        extraction_obj = None
        try:
            extraction_obj = extract_structured_fields(text, new_category)
            raw_fields = extraction_obj.to_flat_dict()
            raw_conf = extraction_obj.get_field_confidences()
            extracted_fields = {k: v for k, v in raw_fields.items() if v is not None}
            extracted_confidences = {k: v for k, v in raw_conf.items() if k in extracted_fields}
        except Exception:
            pass

        # 1. Update PostgreSQL (authoritative)
        if doc is not None:
            doc.classification = new_category
            doc.classification_confidence = new_confidence
            doc.processed_at = utc_now()
            if extracted_fields and extraction_obj is not None:
                run = create_extraction_run(
                    db,
                    document_id=doc.id,
                    status=ExtractionStatus.SUCCESS,
                    document_type=new_category,
                )
                persist_extraction_result(
                    db,
                    doc.id,
                    extraction_obj,
                    extraction_run_id=run.id,
                    document_type=new_category,
                )
                doc.status = DocumentStatus.EXTRACTED
            else:
                doc.status = DocumentStatus.CLASSIFIED
            db.commit()
            db.refresh(doc)

        # 2. Update JSON sidecar (only when legacy compatibility mode is active)
        if _legacy_fallback_enabled():
            metadata["category"] = new_category
            metadata["confidence"] = new_confidence
            metadata["is_manually_corrected"] = False
            if extracted_fields:
                metadata["extracted_fields"] = extracted_fields
                metadata["extracted_confidence"] = extracted_confidences
                metadata["status"] = "EXTRACTED"
            else:
                metadata.pop("extracted_fields", None)
                metadata.pop("extracted_confidence", None)
                metadata["status"] = "CLASSIFIED"

            if metadata_path.parent.is_dir():
                try:
                    with open(metadata_path, "w", encoding="utf-8") as f:
                        json.dump(metadata, f, indent=2)
                except Exception:
                    pass

        if doc is not None:
            return {
                "document_id": doc.id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "storage_path": doc.storage_path,
                "status": doc.status.value,
                "uploaded_at": doc.upload_timestamp.isoformat().replace("+00:00", "Z"),
                "submitter_id": doc.uploaded_by,
                "organization_id": doc.organization_id,
                "category": doc.classification,
                "confidence": doc.classification_confidence,
                "extracted_fields": extracted_fields,
                "extracted_confidence": extracted_confidences,
                "is_manually_corrected": False,
            }

        # Legacy-only: document only in JSON sidecar
        if _legacy_fallback_enabled():
            return metadata

        raise HTTPException(status_code=404, detail="Document not found")

    except (ExtractionError, ClassificationError) as exc:
        raise HTTPException(status_code=422, detail=f"Classification failed: {exc}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Classification failed: {exc}")


# ---------------------------------------------------------------------------
# DELETE /api/documents/{document_id} — delete document and cascade records
# ---------------------------------------------------------------------------

@router.delete("/{document_id}")
async def delete_document_endpoint(
    document_id: str,
    user: Annotated[dict, Depends(require_submitter)],
    db: Session = Depends(get_db),
):
    """Delete a document and its storage binary following authorization and tenant isolation rules."""
    storage = DocumentStorage()
    doc = db.query(Document).filter(Document.id == document_id).first()

    if doc is not None:
        user_org = user.get("organization_id")
        if user_org and doc.organization_id != user_org:
            raise HTTPException(status_code=403, detail="Access denied for this document's organization.")
        db.delete(doc)
        db.commit()

    # Delete storage binary if present
    try:
        file_path = storage.resolve(document_id)
        file_path.unlink(missing_ok=True)
    except DocumentNotFoundError:
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")

    # Clean up any legacy metadata file
    meta_file = storage.base_dir / "metadata" / f"{document_id}.json"
    if meta_file.exists():
        meta_file.unlink(missing_ok=True)

    return {"message": "Document deleted successfully", "document_id": document_id}
