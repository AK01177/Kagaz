"""Pydantic schemas for Kagaz backend."""
from app.schemas.document import (
    DocumentMetadataCreate,
    DocumentMetadataResponse,
    DocumentStatusUpdate,
)
from app.schemas.extraction import (
    ExtractionBase,
    ExtractionCreate,
    ExtractionResponse,
    DocumentExtractionsResponse,
    ExtractedField,
    BaseDocumentExtraction,
    InvoiceExtraction,
    ResumeExtraction,
    ExtractionDocumentType,
    EXTRACTION_SCHEMA_REGISTRY,
    get_extraction_schema,
    get_supported_extraction_types,
    get_field_definitions,
)

__all__ = [
    "DocumentMetadataCreate",
    "DocumentMetadataResponse",
    "DocumentStatusUpdate",
    "ExtractionBase",
    "ExtractionCreate",
    "ExtractionResponse",
    "DocumentExtractionsResponse",
    "ExtractedField",
    "BaseDocumentExtraction",
    "InvoiceExtraction",
    "ResumeExtraction",
    "ExtractionDocumentType",
    "EXTRACTION_SCHEMA_REGISTRY",
    "get_extraction_schema",
    "get_supported_extraction_types",
    "get_field_definitions",
]
