"""CRUD modules for Kagaz backend."""
from app.crud.document import (
    create_document_metadata,
    get_document_metadata,
    update_document_status,
)
from app.crud.extraction import (
    create_extraction,
    create_extractions_bulk,
    get_extractions_by_document,
    get_document_extractions_summary,
    delete_extractions_by_document,
)

__all__ = [
    "create_document_metadata",
    "get_document_metadata",
    "update_document_status",
    "create_extraction",
    "create_extractions_bulk",
    "get_extractions_by_document",
    "get_document_extractions_summary",
    "delete_extractions_by_document",
]
