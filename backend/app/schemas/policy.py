from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, validator

from app.models.policy import PolicyClassification, PolicyVersionStatus
from services.document_types import require_document_type


class PolicyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Policy title")
    domain: str = Field(..., min_length=1, max_length=50, description="Domain (financial, hr, academic, compliance)")
    content: str = Field(..., min_length=1, description="Policy text or rule definitions")
    description: Optional[str] = Field(None, max_length=500, description="Brief policy description")
    document_type: Optional[str] = Field(
        None, max_length=100, description="Document type this policy applies to; empty means every type"
    )
    classification: PolicyClassification = Field(
        PolicyClassification.INTERNAL, description="Who may read this policy"
    )


class PolicyCreate(PolicyBase):
    @field_validator("document_type")
    @classmethod
    def document_type_is_a_known_category(cls, value: Optional[str]) -> Optional[str]:
        return require_document_type(value)


class PolicyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    domain: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    content: Optional[str] = Field(None, min_length=1)
    document_type: Optional[str] = Field(None, max_length=100)
    classification: Optional[PolicyClassification] = None
    changelog: Optional[str] = Field(None, description="Notes on what changed in this version")
    is_active: Optional[bool] = None

    @field_validator("document_type")
    @classmethod
    def document_type_is_a_known_category(cls, value: Optional[str]) -> Optional[str]:
        return require_document_type(value)


class PolicyVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    policy_id: str
    version: str
    content: Optional[str] = None  # None for versions uploaded as files
    status: PolicyVersionStatus
    ingestion_error: Optional[str] = None
    changelog: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime


class PolicyResponse(PolicyBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    current_version: str
    is_active: bool
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PolicyRetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    domain: str | None = Field(default=None, max_length=100)
    document_type: str | None = Field(default=None, max_length=100)
    policy_version: str | None = Field(default=None, max_length=50)
    limit: int = Field(default=5, ge=1, le=20)

    @validator("query")
    def query_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be blank")
        return value


class PolicyEvidence(BaseModel):
    policy_id: str
    version: str
    score: float
    content: str
    page_number: int | None
    section: str | None
    chunk_index: int
    metadata: dict[str, Any]
    source_document_id: str | None
    source_filename: str | None


class PolicyRetrievalResponse(BaseModel):
    outcome: str
    results: list[PolicyEvidence] = Field(default_factory=list)
    message: str | None = None


class PolicyIngestionResponse(BaseModel):
    """Result for a submitted or retried policy version."""
    policy_id: str
    policy_version_id: str
    source_document_id: str | None  # None for policies entered as text
    source_filename: str | None
    version: str
    status: str
    chunk_count: int = 0
    ingestion_error: str | None = None


class PolicyVersionSummary(BaseModel):
    """Status and source details returned for one policy version."""
    created_at: datetime | None = None
    policy_version_id: str
    source_document_id: str | None  # None for policies entered as text
    source_filename: str | None
    version: str
    status: str
    chunk_count: int = 0
    ingestion_error: str | None = None
