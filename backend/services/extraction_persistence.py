"""
BE-05 & DB-03: Persist Extraction Results
Service layer that receives a populated BaseDocumentExtraction object,
converts it into ExtractionCreate records, and persists them via
app.crud.extraction.create_extractions_bulk.

Design notes
- Idempotent on repeated calls: existing field records for the document
  are deleted before bulk-inserting the new set, so re-running extraction
  never produces duplicate-key errors.
- DB-03: Records discrete ExtractionRun instances, establishing the
  Document -> Extraction Run -> Extracted Fields hierarchy.
- Failed extraction attempts do not corrupt previous successful results:
  calling record_failed_extraction_run preserves existing extractions.
- Persistence failures propagate as ExtractionPersistenceError; callers
  must NOT silently swallow them — they should return a controlled error
  response so the document is not marked EXTRACTED while its fields are
  missing from the database.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.crud.extraction import (
    create_extraction_run,
    create_extractions_bulk,
    delete_extractions_by_document,
    get_document_extractions_summary,
    get_extraction_runs_by_document,
    get_latest_extraction_run,
)
from app.models.document import Document
from app.models.extraction import ExtractionRun, ExtractionStatus
from app.schemas.extraction import (
    BaseDocumentExtraction,
    DocumentExtractionsResponse,
    ExtractionCreate,
)

logger = logging.getLogger(__name__)


class ExtractionPersistenceError(Exception):
    """Raised when extraction records cannot be saved to the database."""


def persist_extraction_result(
    db: Session,
    document_id: str,
    extraction: BaseDocumentExtraction,
    extraction_run_id: Optional[str] = None,
    document_type: Optional[str] = None,
) -> List[ExtractionCreate]:
    """Convert a structured extraction result and persist it to the database.

    Replaces existing active extraction records for the document so that
    re-running extraction is idempotent, while maintaining an audit run entry.

    Args:
        db: Active SQLAlchemy session.
        document_id: Identifier of the parent document.
        extraction: Populated schema instance from the extraction service.
        extraction_run_id: Optional ID of an existing extraction run.
        document_type: Optional classification type string.

    Returns:
        List of ExtractionCreate objects that were persisted.

    Raises:
        ExtractionPersistenceError: When the database operation fails.
    """
    flat_values = extraction.to_flat_dict()
    confidences = extraction.get_field_confidences()

    records: List[ExtractionCreate] = []
    for field_name, raw_value in flat_values.items():
        # Skip fields that were not extracted (None / empty list)
        if raw_value is None:
            continue
        # Convert list values (e.g. skills) to a JSON-safe string
        if isinstance(raw_value, list):
            value_str = ", ".join(str(v) for v in raw_value) if raw_value else ""
        else:
            value_str = str(raw_value).strip()

        if not value_str:
            continue

        records.append(
            ExtractionCreate(
                field_name=field_name,
                value=value_str,
                confidence=confidences.get(field_name, 0.0),
            )
        )

    try:
        # If extraction_run_id is not provided, verify document exists and create run
        if extraction_run_id is None:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc is not None:
                doc_type = document_type or doc.classification
                run = create_extraction_run(
                    db,
                    document_id=document_id,
                    status=ExtractionStatus.SUCCESS,
                    document_type=doc_type,
                )
                extraction_run_id = run.id

        # Delete existing records first to keep the operation idempotent
        deleted = delete_extractions_by_document(db, document_id)
        if deleted:
            logger.info(
                "Replaced %d existing extraction record(s) for document %s",
                deleted,
                document_id,
            )

        create_extractions_bulk(
            db,
            document_id=document_id,
            extractions_data=records,
            extraction_run_id=extraction_run_id,
        )
        logger.info(
            "Persisted %d extraction field(s) for document %s (run %s)",
            len(records),
            document_id,
            extraction_run_id,
        )
    except Exception as exc:
        db.rollback()
        logger.exception(
            "Failed to persist extraction results for document %s", document_id
        )
        raise ExtractionPersistenceError(
            f"Could not persist extraction results for document '{document_id}': {exc}"
        ) from exc

    return records


def record_failed_extraction_run(
    db: Session,
    document_id: str,
    document_type: Optional[str] = None,
    error_message: Optional[str] = None,
) -> ExtractionRun:
    """Record a failed extraction attempt without corrupting previous successful extractions."""
    try:
        run = create_extraction_run(
            db,
            document_id=document_id,
            status=ExtractionStatus.FAILED,
            document_type=document_type,
            error_message=error_message,
        )
        logger.warning(
            "Recorded failed extraction run %s for document %s: %s",
            run.id,
            document_id,
            error_message,
        )
        return run
    except Exception as exc:
        db.rollback()
        logger.exception(
            "Failed to record extraction run failure for document %s", document_id
        )
        raise ExtractionPersistenceError(
            f"Could not record extraction run failure for '{document_id}': {exc}"
        ) from exc


def get_extraction_response(
    db: Session,
    document_id: str,
) -> DocumentExtractionsResponse | None:
    """Fetch and format stored extraction records for the API response.

    Returns None when the document does not exist in the database.
    Returns an empty-fields response when the document exists but has
    no stored extractions yet (e.g. still processing).
    """
    return get_document_extractions_summary(db, document_id)
