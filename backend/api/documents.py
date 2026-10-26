"""
Document API endpoints.

Sprint 2 additions
- BE-04: PATCH /{id}/classification — correction now requires a valid reviewer
  JWT (or falls back to dev identity). Auth guard added.
- BE-06: GET /{id}/extract — returns stored structured extraction fields from
  the JSON metadata store (JSON-file backend; wired to DB when PostgreSQL
  is live).
- BE-07: POST upload now accepts PDF, PNG, JPG and JPEG (validation handled
  in services/upload.py).
"""
from datetime import datetime, timezone
import json
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from api.auth import require_reviewer, require_submitter
from api.upload_limit import UploadLimitRoute
from services.classification import ClassificationError, DocumentCategory, classify_document
from services.extraction import ExtractionError, extract_text
from services.upload import UploadError, save_upload
from storage.document_storage import DocumentStorage


router = APIRouter(prefix="/api/documents", tags=["documents"], route_class=UploadLimitRoute)


class ClassificationCorrectionRequest(BaseModel):
    category: str = Field(..., description="The corrected document category.")
    notes: Optional[str] = Field(None, description="Optional reviewer notes or rationale for correction.")


# ---------------------------------------------------------------------------
# POST /api/documents — upload a document (BE-07: PDF + image support)
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def upload_document(
    user: Annotated[dict, Depends(require_submitter)],
    file: Annotated[UploadFile | None, File()] = None,
):
    try:
        if file is None:
            raise UploadError(400, "INVALID_FILE", "A file is required.")
        return await run_in_threadpool(save_upload, file, DocumentStorage(), user)
    except UploadError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )
    finally:
        if file is not None:
            await file.close()


# ---------------------------------------------------------------------------
# GET /api/documents/{document_id} — fetch document metadata
# ---------------------------------------------------------------------------

@router.get("/{document_id}")
async def get_document(document_id: str):
    storage = DocumentStorage()
    metadata_path = storage.base_dir / "metadata" / f"{document_id}.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not read metadata")


# ---------------------------------------------------------------------------
# PATCH /api/documents/{document_id}/classification — BE-04: correction
# ---------------------------------------------------------------------------

@router.patch("/{document_id}/classification")
async def correct_classification(
    document_id: str,
    payload: ClassificationCorrectionRequest,
    user: Annotated[dict, Depends(require_reviewer)],
):
    """Correct a document's classification.

    BE-04: Only active users with the REVIEWER (or higher) role may call
    this endpoint.  The previous and new values are written into
    ``classification_history`` for full audit traceability.
    """
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

    try:
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not update document metadata")

    return metadata


# ---------------------------------------------------------------------------
# GET /api/documents/{document_id}/extract — BE-06: extraction results
# ---------------------------------------------------------------------------

@router.get("/{document_id}/extract")
async def get_extraction_results(
    document_id: str,
    user: Annotated[dict, Depends(require_reviewer)],
):
    """Return stored structured extraction fields for a document.

    BE-06: Response shape matches the contract in docs/api-design.md.
    Fields and confidence values are read from the document's JSON metadata
    (populated when structured extraction runs).  When no fields have been
    extracted yet the ``fields`` and ``confidence`` dicts are empty.

    Response (200):
    {
      "document_id": "doc_001",
      "document_type": "financial",
      "fields": {"invoice_number": "INV-1042", ...},
      "confidence": {"invoice_number": 0.97, ...},
      "status": "EXTRACTED"
    }
    """
    storage = DocumentStorage()
    metadata_path = storage.base_dir / "metadata" / f"{document_id}.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not read metadata")

    # Read stored extraction fields (set by the structured extraction service)
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
# POST /api/documents/{document_id}/classify — re-run classification
# ---------------------------------------------------------------------------

@router.post("/{document_id}/classify")
async def reclassify_document(document_id: str):
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
