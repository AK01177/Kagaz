from typing import Any

from pydantic import BaseModel, Field, validator


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


class PolicyIngestionResponse(BaseModel):
    """Result for a submitted or retried policy version."""
    policy_id: str
    policy_version_id: str
    source_document_id: str
    source_filename: str
    version: str
    status: str
    chunk_count: int = 0
    ingestion_error: str | None = None


class PolicyVersionSummary(BaseModel):
    """Status and source details returned for one policy version."""
    policy_version_id: str
    source_document_id: str
    source_filename: str
    version: str
    status: str
    chunk_count: int = 0
    ingestion_error: str | None = None
