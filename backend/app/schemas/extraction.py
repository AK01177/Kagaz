"""
AI-05: Define Extraction Schemas
Defines structured field extraction schemas, per-field confidence scoring,
and document-type schema registry for Kagaz.
Also includes persistence-layer schemas used by DB-01 extraction storage.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T")


class ExtractedField(BaseModel, Generic[T]):
    """
    Standard container for an extracted field.
    Provides typed value, extraction confidence (0.0 - 1.0), raw text evidence,
    and presence tracking for reliable downstream validation and review.
    """

    value: Optional[T] = Field(
        default=None,
        description="Extracted value matching expected type, or None if missing or unidentifiable.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Model confidence score between 0.0 (unconfident / missing) and 1.0 (highest confidence).",
    )
    raw_value: Optional[str] = Field(
        default=None,
        description="Unprocessed text snippet from document matching this field, preserving source context.",
    )
    is_present: bool = Field(
        default=False,
        description="Whether the field was successfully detected and present in the document.",
    )

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def sync_presence(self) -> ExtractedField[T]:
        if self.value is not None and not self.is_present:
            self.is_present = True
        elif self.value is None:
            self.is_present = False
        return self

    @classmethod
    def present(
        cls,
        value: T,
        confidence: float = 1.0,
        raw_value: Optional[str] = None,
    ) -> ExtractedField[T]:
        """Convenience constructor for a successfully extracted field."""
        return cls(
            value=value,
            confidence=confidence,
            raw_value=raw_value or (str(value) if value is not None else None),
            is_present=True,
        )

    @classmethod
    def missing(cls) -> ExtractedField[T]:
        """Convenience constructor for an absent or unidentifiable field."""
        return cls(
            value=None,
            confidence=0.0,
            raw_value=None,
            is_present=False,
        )


class BaseDocumentExtraction(BaseModel):
    """
    Base class for document-type extraction models.
    Provides utility methods for API serialization, missing-field inspection,
    and confidence aggregation.
    """

    model_config = ConfigDict(extra="ignore")

    def to_flat_dict(self) -> Dict[str, Any]:
        """Return a simplified dictionary of field_name -> value."""
        result: Dict[str, Any] = {}
        for field_name in type(self).model_fields:
            field_obj = getattr(self, field_name)
            if isinstance(field_obj, ExtractedField):
                result[field_name] = field_obj.value
            else:
                result[field_name] = field_obj
        return result

    def get_field_confidences(self) -> Dict[str, float]:
        """Return a dictionary of field_name -> confidence score."""
        confidences: Dict[str, float] = {}
        for field_name in type(self).model_fields:
            field_obj = getattr(self, field_name)
            if isinstance(field_obj, ExtractedField):
                confidences[field_name] = field_obj.confidence
        return confidences

    def get_missing_fields(self) -> List[str]:
        """Return names of required/defined fields that were not extracted."""
        missing: List[str] = []
        for field_name in type(self).model_fields:
            field_obj = getattr(self, field_name)
            if isinstance(field_obj, ExtractedField) and (not field_obj.is_present or field_obj.value is None):
                missing.append(field_name)
        return missing

    def average_confidence(self) -> float:
        """Calculate mean confidence across all fields defined in the schema."""
        scores = [
            getattr(self, field_name).confidence
            for field_name in type(self).model_fields
            if isinstance(getattr(self, field_name), ExtractedField)
        ]
        return round(sum(scores) / len(scores), 4) if scores else 0.0


class InvoiceExtraction(BaseDocumentExtraction):
    """
    Structured extraction schema for Invoice documents.
    Covers essential fields for validation and review.
    """

    invoice_number: ExtractedField[str] = Field(
        default_factory=ExtractedField,
        description="The unique invoice identifier or reference number.",
    )
    invoice_date: ExtractedField[str] = Field(
        default_factory=ExtractedField,
        description="Issue or billing date of the invoice (ISO format YYYY-MM-DD preferred).",
    )
    supplier_name: ExtractedField[str] = Field(
        default_factory=ExtractedField,
        description="Name of the vendor, contractor, or organization issuing the invoice.",
    )
    total_amount: ExtractedField[float] = Field(
        default_factory=ExtractedField,
        description="Total monetary balance due or paid on the invoice.",
    )


class ResumeExtraction(BaseDocumentExtraction):
    """
    Structured extraction schema for Resume / HR Form documents.
    Extracts candidate contact information and qualifications.
    """

    candidate_name: ExtractedField[str] = Field(
        default_factory=ExtractedField,
        description="Full name of the candidate / applicant.",
    )
    email: ExtractedField[str] = Field(
        default_factory=ExtractedField,
        description="Contact email address of the applicant.",
    )
    phone: ExtractedField[str] = Field(
        default_factory=ExtractedField,
        description="Contact phone number.",
    )
    skills: ExtractedField[List[str]] = Field(
        default_factory=lambda: ExtractedField(value=[]),
        description="List of detected technical and professional competencies.",
    )


class ExtractionBase(BaseModel):
    """Persistence-layer schema for a single extracted document field."""

    field_name: str
    value: str
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )


class ExtractionCreate(ExtractionBase):
    pass


class ExtractionResponse(ExtractionBase):
    id: str
    document_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentExtractionsResponse(BaseModel):
    """Structured extraction summary as specified in api-design.md GET /api/documents/{id}/extract."""

    document_id: str
    document_type: Optional[str] = None
    fields: Dict[str, str] = Field(default_factory=dict)
    confidence: Dict[str, float] = Field(default_factory=dict)


class ExtractionDocumentType(str, enum.Enum):
    """Supported document types for structured AI extraction."""

    INVOICE = "invoice"
    RESUME = "resume"
    HR_FORM = "hr_form"


# Registry mapping canonical names and aliases to their extraction schema
EXTRACTION_SCHEMA_REGISTRY: Dict[str, type[BaseDocumentExtraction]] = {
    ExtractionDocumentType.INVOICE.value: InvoiceExtraction,
    ExtractionDocumentType.RESUME.value: ResumeExtraction,
    ExtractionDocumentType.HR_FORM.value: ResumeExtraction,
    "financial": InvoiceExtraction,
    "hr_documents": ResumeExtraction,
    "academics": ResumeExtraction,
    "general_confidential": ResumeExtraction,
}


def get_extraction_schema(document_type: str | ExtractionDocumentType) -> Optional[type[BaseDocumentExtraction]]:
    """
    Retrieve the extraction schema class for a given document type.
    Normalizes case, whitespace, and handles Enum inputs. Returns None if type is unsupported.
    """
    if document_type is None:
        return None
    if isinstance(document_type, enum.Enum):
        normalized = str(document_type.value).strip().lower()
    else:
        normalized = str(document_type).strip().lower()
    return EXTRACTION_SCHEMA_REGISTRY.get(normalized)


def get_supported_extraction_types() -> List[str]:
    """Return list of distinct supported document type names."""
    return sorted(list(EXTRACTION_SCHEMA_REGISTRY.keys()))


def get_field_definitions(document_type: str | ExtractionDocumentType) -> Dict[str, Dict[str, Any]]:
    """
    Return metadata definition for each field in the document type's schema,
    including type, description, and default presence.
    Useful for LLM prompts, frontend form generation, and validation contracts.
    """
    schema_cls = get_extraction_schema(document_type)
    if not schema_cls:
        return {}

    definitions: Dict[str, Dict[str, Any]] = {}
    for name, field_info in schema_cls.model_fields.items():
        definitions[name] = {
            "name": name,
            "description": field_info.description or "",
        }
    return definitions
