from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from services.upload import UploadError, save_upload
from storage.document_storage import DocumentStorage
from api.auth import require_submitter


router = APIRouter(prefix="/api/documents", tags=["documents"])


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
