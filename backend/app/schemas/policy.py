from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, validator


class PolicyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Policy title")
    domain: str = Field(..., min_length=1, max_length=50, description="Domain (financial, hr, academic, compliance)")
    content: str = Field(..., min_length=1, description="Policy text or rule definitions")
    description: Optional[str] = Field(None, max_length=500, description="Brief policy description")


class PolicyCreate(PolicyBase):
    pass


class PolicyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    domain: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    content: Optional[str] = Field(None, min_length=1)
    changelog: Optional[str] = Field(None, description="Notes on what changed in this version")
    is_active: Optional[bool] = None


class PolicyVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    policy_id: str
    version: str
    content: str
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
    source_document_id: str
    source_filename: str


class PolicyRetrievalResponse(BaseModel):
    outcome: str
    results: list[PolicyEvidence] = Field(default_factory=list)
    message: str | None = None
