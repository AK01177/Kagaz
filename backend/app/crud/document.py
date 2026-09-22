"""
CRUD operations for document metadata.
"""

from sqlalchemy.orm import Session

from app.models.document import Document
from app.schemas.document import (
    DocumentMetadataCreate,
    DocumentStatusUpdate,
)


def create_document_metadata(
    db: Session,
    document_data: DocumentMetadataCreate,
) -> Document:
    """Create and persist a new document metadata record."""

    document = Document(
        organization_id=str(document_data.organization_id),
        uploaded_by=str(document_data.uploaded_by),
        filename=document_data.filename,
        file_type=document_data.file_type,
        file_size=document_data.file_size,
        storage_path=document_data.storage_path,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


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


def update_document_status(
    db: Session,
    document_id: str,
    organization_id: str,
    update_data: DocumentStatusUpdate,
) -> Document | None:
    """
    Update document status and classification metadata.

    The organization ID check ensures that one organization
    cannot modify another organization's document.
    """

    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.organization_id == str(organization_id),
        )
        .first()
    )

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

    db.commit()
    db.refresh(document)

    return document