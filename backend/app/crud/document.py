"""
CRUD operations for document metadata.
"""
import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.schemas.document import (
    DocumentMetadataCreate,
    DocumentStatusUpdate,
)


def create_document_metadata(
    db: Session,
    document_data: DocumentMetadataCreate,
    document_id: Optional[str] = None,
) -> Document:
    """Create and persist a new document metadata record."""
    doc_id = document_id or document_data.id or str(uuid.uuid4())
    status_val = document_data.status or DocumentStatus.UPLOADED
    if isinstance(status_val, str):
        try:
            status_val = DocumentStatus(status_val)
        except ValueError:
            status_val = DocumentStatus.UPLOADED

    document = Document(
        id=doc_id,
        organization_id=str(document_data.organization_id),
        uploaded_by=str(document_data.uploaded_by),
        filename=document_data.filename,
        file_type=document_data.file_type,
        file_size=document_data.file_size,
        storage_path=document_data.storage_path,
        status=status_val,
        classification=document_data.classification,
        classification_confidence=document_data.classification_confidence,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def get_document_metadata(
    db: Session,
    document_id: str,
    organization_id: Optional[str] = None,
) -> Document | None:
    """
    Retrieve document metadata by document ID and optional organization ID.
    If organization_id is provided, enforces tenant isolation.
    """
    query = db.query(Document).filter(Document.id == document_id)
    if organization_id is not None:
        query = query.filter(Document.organization_id == str(organization_id))
    return query.first()


def update_document_status(
    db: Session,
    document_id: str,
    organization_id: Optional[str] = None,
    update_data: Optional[DocumentStatusUpdate] = None,
) -> Document | None:
    """
    Update document status and classification metadata.
    """
    document = get_document_metadata(db, document_id, organization_id)
    if document is None:
        return None

    if update_data is not None:
        if update_data.status is not None:
            document.status = update_data.status
        if update_data.classification is not None:
            document.classification = update_data.classification
        if update_data.classification_confidence is not None:
            document.classification_confidence = update_data.classification_confidence

    db.commit()
    db.refresh(document)

    return document
