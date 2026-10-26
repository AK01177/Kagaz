"""
BE-05: Persist Extraction Results
Service layer that receives a populated BaseDocumentExtraction object,
converts it into ExtractionCreate records, and persists them via
app.crud.extraction.create_extractions_bulk.

Design notes
- Idempotent on repeated calls: existing field records for the document
  are deleted before bulk-inserting the new set, so re-running extraction
  never produces duplicate-key errors.
- Persistence failures propagate as ExtractionPersistenceError; callers
  must NOT silently swallow them — they should return a controlled error
  response so the document is not marked EXTRACTED while its fields are
  missing from the database.
"""
from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session

from app.crud.extraction import (
    create_extractions_bulk,
    delete_extractions_by_document,
    get_document_extractions_summary,
)
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
) -> List[ExtractionCreate]:
    """Convert a structured extraction result and persist it to the database.

    Replaces any existing extraction records for the document so that
    re-running extraction is idempotent.

    Args:
        db: Active SQLAlchemy session.
        document_id: Identifier of the parent document.
        extraction: Populated schema instance from the extraction service.

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
        # Delete existing records first to keep the operation idempotent
        deleted = delete_extractions_by_document(db, document_id)
        if deleted:
            logger.info(
                "Replaced %d existing extraction record(s) for document %s",
                deleted,
                document_id,
            )

        create_extractions_bulk(db, document_id, records)
        logger.info(
            "Persisted %d extraction field(s) for document %s",
            len(records),
            document_id,
        )
    except Exception as exc:
        logger.exception(
            "Failed to persist extraction results for document %s", document_id
        )
        raise ExtractionPersistenceError(
            f"Could not persist extraction results for document '{document_id}': {exc}"
        ) from exc

    return records


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
