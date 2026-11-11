"""
Pydantic schemas for Document and Policy Assistant API (BE-14).
"""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssistantQueryRequest(BaseModel):
    """User question submitted to the document and policy assistant."""
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Question regarding document contents, extracted data, or policy compliance.",
    )

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Question cannot be blank or whitespace only.")
        return stripped


class AssistantSourceReference(BaseModel):
    """Grounded reference supporting an assistant answer."""
    model_config = ConfigDict(from_attributes=True)

    source_type: str = Field(
        ...,
        description="Type of source: DOCUMENT_FIELD, POLICY_CHUNK, or VALIDATION_FINDING",
    )
    title: str
    reference: str
    excerpt: str
    policy_id: Optional[str] = None
    policy_name: Optional[str] = None
    policy_version: Optional[str] = None
    page_number: Optional[int] = None
    section: Optional[str] = None


class AssistantQueryResponse(BaseModel):
    """Grounded response with source citations and policy evidence."""
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    question: str
    answer: str
    sources: List[AssistantSourceReference] = Field(default_factory=list)
    is_grounded: bool = True
    limitation: Optional[str] = None
    confidence: Optional[float] = None
