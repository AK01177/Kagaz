"""
API routes for document metadata (BE-03).

Does NOT include the upload endpoint itself (multipart upload, S3
write) — that belongs to BE-02, Document Ingestion. This router only
covers metadata retrieval once a document record already exists.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import Permission, require_permission
from app.crud.document import get_document_metadata
from app.db.session import get_db
from app.schemas.document import DocumentMetadataResponse

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}", response_model=DocumentMetadataResponse)
def read_document_metadata(
    document_id: uuid.UUID,
    user: Annotated[dict, Depends(require_permission(Permission.DOCUMENTS_READ))],
    db: Session = Depends(get_db),
):
    """Retrieve metadata for a single uploaded document, scoped to the caller's active organization."""
    organization_id = str(user["organization_id"])
    document = get_document_metadata(db, str(document_id), organization_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
