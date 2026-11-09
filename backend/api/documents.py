"""
Document API endpoints.

Sprint 2 additions:
- BE-04: PATCH /{id}/classification — correction requires valid reviewer JWT.
- BE-06: GET /{id}/extract — returns stored structured extraction fields.
- BE-07: POST upload accepts PDF, PNG, JPG and JPEG.

Sprint 3 additions:
- DB-03: PostgreSQL document metadata and extraction persistence integration.
"""
from datetime import datetime, timezone
import json
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from api.auth import require_reviewer, require_submitter
from api.upload_limit import UploadLimitRoute
from app.db.session import get_db
from services.classification import ClassificationError, DocumentCategory, classify_document
from services.extraction import ExtractionError, extract_text
from services.structured_extraction import (
    StructuredExtractionError,
    UnsupportedDocumentTypeError,
    extract_structured_fields,
)
from services.upload import UploadError, save_upload
from storage.document_storage import DocumentNotFoundError, DocumentStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"], route_class=UploadLimitRoute)


class ClassificationCorrectionRequest(BaseModel):
    category: str = Field(..., description="The corrected document category.")
    notes: Optional[str] = Field(None, description="Optional reviewer notes or rationale for correction.")


# ---------------------------------------------------------------------------
# POST /api/documents — upload a document (BE-07 / DB-03)
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def upload_document(
    user: Annotated[dict, Depends(require_submitter)],
    file: Annotated[UploadFile | None, File()] = None,
    db: Annotated[Session | None, Depends(get_db)] = None,
):
    try:
        if file is None:
            raise UploadError(400, "INVALID_FILE", "A file is required.")
        return await run_in_threadpool(save_upload, file, DocumentStorage(), user, db=db)
    except UploadError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )
    finally:
        if file is not None:
            await file.close()


# ---------------------------------------------------------------------------
# GET /api/documents/{document_id} — fetch document metadata (DB-03)
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


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: Annotated[Session | None, Depends(get_db)] = None,
):
    storage = DocumentStorage()
    metadata_path = storage.base_dir / "metadata" / f"{document_id}.json"

    # Return persisted metadata JSON if available (matches QA-03 specification)
    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            raise HTTPException(status_code=500, detail="Could not read metadata")

    # DB fallback if metadata JSON file is absent
    if db is not None:
        try:
            from app.models.document import Document
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc is not None:
                data = {
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "file_type": doc.file_type,
                    "file_size": doc.file_size,
                    "storage_path": doc.storage_path,
                    "status": doc.status.value if hasattr(doc.status, "value") else str(doc.status),
                    "uploaded_at": doc.upload_timestamp.isoformat().replace("+00:00", "Z") if doc.upload_timestamp else None,
                    "category": doc.classification,
                    "confidence": doc.classification_confidence,
                    "organization_id": doc.organization_id,
                    "submitter_id": doc.uploaded_by,
                }
                from app.crud.extraction import get_extractions_by_document
                extractions = get_extractions_by_document(db, document_id)
                if extractions:
                    data["extracted_fields"] = {e.field_name: e.value for e in extractions}
                    data["extracted_confidence"] = {e.field_name: e.confidence for e in extractions}
                    data["status"] = "EXTRACTED"
                return data
        except Exception as e:
            logger.debug("DB document lookup fallback for %s: %s", document_id, e)

    raise HTTPException(status_code=404, detail="Document not found")


# ---------------------------------------------------------------------------
# PATCH /api/documents/{document_id}/classification — BE-04 / DB-03
# ---------------------------------------------------------------------------

@router.patch("/{document_id}/classification")
async def correct_classification(
    document_id: str,
    payload: ClassificationCorrectionRequest,
    user: Annotated[dict, Depends(require_reviewer)],
    db: Annotated[Session | None, Depends(get_db)] = None,
):
    """Correct a document's classification."""
    storage = DocumentStorage()
    metadata_path = storage.base_dir / "metadata" / f"{document_id}.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    valid_categories = [c.value for c in DocumentCategory]
    normalized_category = payload.category.strip().lower()
    if normalized_category not in valid_categories:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid category '{payload.category}'. Valid categories are: {', '.join(valid_categories)}",
        )

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not read metadata")

    previous_category = metadata.get("category")
    previous_confidence = metadata.get("confidence")

    history = metadata.get("classification_history", [])
    history.append({
        "previous_category": previous_category,
        "previous_confidence": previous_confidence,
        "updated_category": normalized_category,
        "corrected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "notes": payload.notes,
        "corrected_by": user.get("sub", "reviewer"),
    })

    metadata["category"] = normalized_category
    metadata["confidence"] = 1.0
    metadata["status"] = "CLASSIFIED"
    metadata["is_manually_corrected"] = True
    metadata["last_corrected_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    metadata["classification_history"] = history

    extraction = None
    try:
        text = extract_text(document_id, storage)
        extraction = extract_structured_fields(text, normalized_category)
        metadata["extracted_fields"] = extraction.to_flat_dict()
        metadata["extracted_confidence"] = extraction.get_field_confidences()
        metadata["status"] = "EXTRACTED"
    except Exception:
        metadata.pop("extracted_fields", None)
        metadata.pop("extracted_confidence", None)
        metadata["status"] = "CLASSIFIED"

    # DB-03: Persist classification and extraction update to DB
    if db is not None:
        try:
            from app.models.document import Document, DocumentStatus
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc is not None:
                doc.classification = normalized_category
                doc.classification_confidence = 1.0
                doc.status = DocumentStatus.CLASSIFIED
                db.commit()
                if extraction is not None:
                    from services.extraction_persistence import persist_extraction_result
                    persist_extraction_result(db, document_id, extraction)
        except Exception as e:
            logger.debug("DB classification update fallback for %s: %s", document_id, e)

    try:
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not update document metadata")

    return metadata


# ---------------------------------------------------------------------------
# GET /api/documents/{document_id}/extract — BE-06 / DB-03
# ---------------------------------------------------------------------------

@router.get("/{document_id}/extract")
async def get_extraction_results(
    document_id: str,
    user: Annotated[dict, Depends(require_reviewer)],
    db: Annotated[Session | None, Depends(get_db)] = None,
):
    """Return stored structured extraction fields for a document."""
    storage = DocumentStorage()
    metadata_path = storage.base_dir / "metadata" / f"{document_id}.json"
    metadata = {}
    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            raise HTTPException(status_code=500, detail="Could not read metadata")

    # If neither metadata JSON nor DB has the document, return 404
    fields: dict = metadata.get("extracted_fields", {})
    confidence: dict = metadata.get("extracted_confidence", {})
    doc_type = metadata.get("category")

    # DB-03: Check database for stored extractions if not found in JSON
    if db is not None:
        try:
            from app.crud.extraction import get_document_extractions_summary
            summary = get_document_extractions_summary(db, document_id)
            if summary is not None:
                doc_type = summary.document_type or doc_type
                if summary.fields:
                    fields = summary.fields
                    confidence = summary.confidence
        except Exception as e:
            logger.debug("DB extraction lookup fallback for %s: %s", document_id, e)

    if not metadata and not doc_type:
        raise HTTPException(status_code=404, detail="Document not found")

    extraction_status = "EXTRACTED" if fields else metadata.get("status", "UPLOADED")

    return {
        "document_id": document_id,
        "document_type": doc_type,
        "fields": fields,
        "confidence": confidence,
        "status": extraction_status,
    }


# ---------------------------------------------------------------------------
# POST /api/documents/{document_id}/extract — re-run structured extraction (DB-03)
# ---------------------------------------------------------------------------

@router.post("/{document_id}/extract")
async def run_extraction(
    document_id: str,
    user: Annotated[dict, Depends(require_reviewer)],
    db: Annotated[Session | None, Depends(get_db)] = None,
):
    """Re-run structured field extraction for an already-classified document."""
    storage = DocumentStorage()
    metadata_path = storage.base_dir / "metadata" / f"{document_id}.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not read metadata")

    try:
        text = await run_in_threadpool(extract_text, document_id, storage)
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=f"Text extraction failed: {exc}")

    document_category = metadata.get("category")
    if not document_category or document_category == "unknown":
        try:
            classification = await run_in_threadpool(classify_document, text)
            document_category = classification.category.value
            metadata["category"] = document_category
            metadata["confidence"] = classification.confidence
            metadata["status"] = "CLASSIFIED"
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
        raise HTTPException(status_code=422, detail=f"Structured extraction failed: {exc}")

    # DB-03: Persist extraction to DB
    if db is not None:
        try:
            from services.extraction_persistence import persist_extraction_result
            persist_extraction_result(db, document_id, extraction_result)
        except Exception as e:
            logger.debug("DB extraction persist fallback for %s: %s", document_id, e)

    metadata["extracted_fields"] = extracted_fields
    metadata["extracted_confidence"] = extracted_confidence
    metadata["status"] = "EXTRACTED"
    metadata["ocr_text_length"] = len(text)

    try:
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not update metadata")

    return {
        "document_id": document_id,
        "document_type": document_category,
        "fields": extracted_fields,
        "confidence": extracted_confidence,
        "status": "EXTRACTED",
        "ocr_text_length": len(text),
    }


# ---------------------------------------------------------------------------
# POST /api/documents/{document_id}/classify — re-run classification (DB-03)
# ---------------------------------------------------------------------------

@router.post("/{document_id}/classify")
async def reclassify_document(
    document_id: str,
    db: Annotated[Session | None, Depends(get_db)] = None,
):
    storage = DocumentStorage()
    metadata_path = storage.base_dir / "metadata" / f"{document_id}.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not read metadata")

    try:
        text = extract_text(document_id, storage)
        result = classify_document(text)
        metadata["category"] = result.category.value
        metadata["confidence"] = result.confidence
        metadata["status"] = "CLASSIFIED"
        metadata["is_manually_corrected"] = False

        extraction = None
        try:
            extraction = extract_structured_fields(text, result.category.value)
            metadata["extracted_fields"] = extraction.to_flat_dict()
            metadata["extracted_confidence"] = extraction.get_field_confidences()
            metadata["status"] = "EXTRACTED"
        except Exception:
            metadata.pop("extracted_fields", None)
            metadata.pop("extracted_confidence", None)
            metadata["status"] = "CLASSIFIED"

        if db is not None:
            try:
                from app.models.document import Document, DocumentStatus
                doc = db.query(Document).filter(Document.id == document_id).first()
                if doc is not None:
                    doc.classification = result.category.value
                    doc.classification_confidence = result.confidence
                    doc.status = DocumentStatus.CLASSIFIED
                    db.commit()
                    if extraction is not None:
                        from services.extraction_persistence import persist_extraction_result
                        persist_extraction_result(db, document_id, extraction)
            except Exception as e:
                logger.debug("DB reclassify fallback for %s: %s", document_id, e)

    except (ExtractionError, ClassificationError) as exc:
        raise HTTPException(status_code=422, detail=f"Classification failed: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Classification failed: {exc}")

    try:
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not update metadata")

    return metadata
