"""Pydantic schemas for document extraction persistence and API responses."""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExtractionBase(BaseModel):
    field_name: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")


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
