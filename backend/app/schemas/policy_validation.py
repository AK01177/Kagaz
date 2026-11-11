"""Stable API schemas for policy validation results."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


FindingStatus = Literal["PASS", "FLAG", "FAIL", "NEEDS_HUMAN_REVIEW", "MISSING_INFORMATION"]
ValidationStatus = Literal["PASS", "FLAG", "FAIL", "NEEDS_HUMAN_REVIEW"]


class PolicyValidationSource(BaseModel):
    reference_type: Literal["POLICY_CHUNK", "DOCUMENT", "RETRIEVAL"] = "POLICY_CHUNK"
    policy_id: str | None = None
    policy_name: str | None = None
    policy_domain: str | None = None
    policy_document_type: str | None = None
    policy_version_id: str | None = None
    policy_version: str | None = None
    source_document_id: str | None = None
    source_filename: str | None = None
    chunk_id: str | None = None
    chunk_index: int | None = None
    page_number: int | None = None
    section: str | None = None
    excerpt: str
    supporting_quote: str | None = None


class PolicyValidationFindingResponse(BaseModel):
    id: str
    status: FindingStatus
    requirement: str
    explanation: str
    field_name: str | None = None
    document_value: str | None = None
    confidence: float | None = None
    sources: list[PolicyValidationSource] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PolicyValidationRunResponse(BaseModel):
    id: str
    document_id: str
    status: ValidationStatus
    summary: str
    retrieval_outcome: str
    policy_versions: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[PolicyValidationFindingResponse] = Field(default_factory=list)
    created_at: datetime


class PolicyValidationQuoteDraft(BaseModel):
    source_chunk_id: str
    quote: str = Field(min_length=12)


class PolicyValidationFindingDraft(BaseModel):
    status: FindingStatus
    requirement: str
    explanation: str
    field_name: str | None = None
    document_value: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_chunk_ids: list[str] = Field(default_factory=list)
    source_quotes: list[PolicyValidationQuoteDraft] = Field(default_factory=list)


class PolicyValidationDraft(BaseModel):
    summary: str
    findings: list[PolicyValidationFindingDraft] = Field(default_factory=list)
