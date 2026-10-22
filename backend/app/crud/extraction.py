"""CRUD operations for document field extractions."""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.extraction import Extraction
from app.schemas.extraction import (
    ExtractionCreate,
    DocumentExtractionsResponse,
)


def create_extraction(
    db: Session,
    document_id: str,
    extraction_data: ExtractionCreate,
) -> Extraction:
    """Create and persist a single extracted field record for a document."""
    record = Extraction(
        document_id=document_id,
        field_name=extraction_data.field_name,
        value=extraction_data.value,
        confidence=extraction_data.confidence,
    )
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except Exception:
        db.rollback()
        raise


def create_extractions_bulk(
    db: Session,
    document_id: str,
    extractions_data: List[ExtractionCreate],
) -> List[Extraction]:
    """Persist multiple extracted field records for a document in a single transaction."""
    if not extractions_data:
        return []

    records = [
        Extraction(
            document_id=document_id,
            field_name=data.field_name,
            value=data.value,
            confidence=data.confidence,
        )
        for data in extractions_data
    ]
    try:
        db.add_all(records)
        db.commit()
        for record in records:
            db.refresh(record)
        return records
    except Exception:
        db.rollback()
        raise


def get_extractions_by_document(
    db: Session,
    document_id: str,
) -> List[Extraction]:
    """Retrieve all extraction records for a document, ordered by field name."""
    return (
        db.query(Extraction)
        .filter(Extraction.document_id == document_id)
        .order_by(Extraction.field_name.asc())
        .all()
    )


def get_document_extractions_summary(
    db: Session,
    document_id: str,
) -> Optional[DocumentExtractionsResponse]:
    """
    Format stored extractions into the API shape defined in docs/api-design.md
    GET /api/documents/{document_id}/extract
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        return None

    records = get_extractions_by_document(db, document_id)
    fields = {r.field_name: r.value for r in records}
    confidence = {r.field_name: r.confidence for r in records}

    return DocumentExtractionsResponse(
        document_id=document_id,
        document_type=doc.classification,
        fields=fields,
        confidence=confidence,
    )


def delete_extractions_by_document(
    db: Session,
    document_id: str,
) -> int:
    """Delete all extraction records for a given document."""
    try:
        deleted_count = (
            db.query(Extraction)
            .filter(Extraction.document_id == document_id)
            .delete(synchronize_session="fetch")
        )
        db.commit()
        return deleted_count
    except Exception:
        db.rollback()
        raise
