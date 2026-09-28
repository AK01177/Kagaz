"""
Pydantic schemas for document metadata — request/response shapes for
the API layer.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus


class DocumentMetadataCreate(BaseModel):
    organization_id: uuid.UUID
    uploaded_by: uuid.UUID
    filename: str
    file_type: str
    file_size: int = Field(gt=0, description="File size in bytes, must be positive")
    storage_path: str


class DocumentMetadataResponse(BaseModel):
    id: str
    organization_id: str
    filename: str
    file_type: str
    file_size: int
    storage_path: str
    status: DocumentStatus
    upload_timestamp: datetime
    classification: Optional[str] = None
    classification_confidence: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentStatusUpdate(BaseModel):
    status: Optional[DocumentStatus] = None
    classification: Optional[str] = None
    classification_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)