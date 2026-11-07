"""
CRUD operations for document metadata.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus, utc_now
from app.schemas.document import (
    DocumentMetadataCreate,
    DocumentStatusUpdate,
)


def create_document(
    db: Session,
    *,
    id: Optional[str] = None,
    organization_id: str,
    uploaded_by: str,
    filename: str,
    file_type: str,
    file_size: int,
    storage_path: str,
    status: DocumentStatus = DocumentStatus.UPLOADED,
    classification: Optional[str] = None,
    classification_confidence: Optional[float] = None,
    processed_at: Optional[datetime] = None,
) -> Document:
    """Create and persist a new document record directly."""
    kwargs = {
        "organization_id": str(organization_id),
        "uploaded_by": str(uploaded_by),
        "filename": filename,
        "file_type": file_type,
        "file_size": file_size,
        "storage_path": storage_path,
        "status": status,
        "classification": classification,
        "classification_confidence": classification_confidence,
        "processed_at": processed_at,
    }
    if id is not None:
        kwargs["id"] = id

    document = Document(**kwargs)
    try:
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
    except Exception:
        db.rollback()
        raise


def create_document_metadata(
    db: Session,
    document_data: DocumentMetadataCreate,
) -> Document:
    """Create and persist a new document metadata record from DocumentMetadataCreate."""
    return create_document(
        db,
        organization_id=str(document_data.organization_id),
        uploaded_by=str(document_data.uploaded_by),
        filename=document_data.filename,
        file_type=document_data.file_type,
        file_size=document_data.file_size,
        storage_path=document_data.storage_path,
    )


def get_document_metadata(
    db: Session,
    document_id: str,
    organization_id: str,
) -> Document | None:
    """
    Retrieve document metadata by document ID and organization ID.

    The organization ID check provides tenant isolation.
    """
    return (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.organization_id == str(organization_id),
        )
        .first()
    )


def get_document_by_id(
    db: Session,
    document_id: str,
) -> Document | None:
    """Retrieve document by document ID without organization scoping."""
    return db.query(Document).filter(Document.id == document_id).first()


def list_documents_by_organization(
    db: Session,
    organization_id: str,
    skip: int = 0,
    limit: int = 100,
) -> list[Document]:
    """Retrieve all documents belonging to an organization, ordered by upload timestamp desc."""
    return (
        db.query(Document)
        .filter(Document.organization_id == str(organization_id))
        .order_by(Document.upload_timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def delete_document(
    db: Session,
    document_id: str,
    organization_id: Optional[str] = None,
) -> bool:
    """Delete a document and cascade its associated extraction runs and fields."""
    query = db.query(Document).filter(Document.id == document_id)
    if organization_id is not None:
        query = query.filter(Document.organization_id == str(organization_id))
    document = query.first()
    if document is None:
        return False
    try:
        db.delete(document)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def update_document_status(
    db: Session,
    document_id: str,
    organization_id: Optional[str],
    update_data: DocumentStatusUpdate,
) -> Document | None:
    """
    Update document status and classification metadata.

    The organization ID check ensures that one organization
    cannot modify another organization's document when provided.
    """
    query = db.query(Document).filter(Document.id == document_id)
    if organization_id is not None:
        query = query.filter(Document.organization_id == str(organization_id))

    document = query.first()
    if document is None:
        return None

    if update_data.status is not None:
        document.status = update_data.status

    if update_data.classification is not None:
        document.classification = update_data.classification

    if update_data.classification_confidence is not None:
        document.classification_confidence = (
            update_data.classification_confidence
        )

    document.processed_at = utc_now()

    try:
        db.commit()
        db.refresh(document)
        return document
    except Exception:
        db.rollback()
        raise
