from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
import json

from services.upload import UploadError, save_upload
from storage.document_storage import DocumentStorage
from api.auth import require_submitter
from api.upload_limit import UploadLimitRoute


router = APIRouter(prefix="/api/documents", tags=["documents"], route_class=UploadLimitRoute)


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

