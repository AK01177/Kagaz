from datetime import datetime, timezone
import json
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from api.auth import require_submitter
from api.upload_limit import UploadLimitRoute
from services.classification import ClassificationError, DocumentCategory, classify_document
from services.extraction import ExtractionError, extract_text
from services.upload import UploadError, save_upload
from storage.document_storage import DocumentStorage


router = APIRouter(prefix="/api/documents", tags=["documents"], route_class=UploadLimitRoute)


class ClassificationCorrectionRequest(BaseModel):
    category: str = Field(..., description="The corrected document category.")
    notes: Optional[str] = Field(None, description="Optional reviewer notes or rationale for correction.")


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


@router.patch("/{document_id}/classification")
async def correct_classification(
    document_id: str,
    payload: ClassificationCorrectionRequest,
):
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
        "corrected_by": "reviewer",
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


