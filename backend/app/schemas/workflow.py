"""
BE-10 / BE-11: Pydantic schemas for workflow and review/approval API responses.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class WorkflowTransitionResponse(BaseModel):
    """Response returned after a successful workflow state transition."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    organization_id: str
    actor_id: str
    actor_role: str
    action: str
    from_status: str
    to_status: str
    comment: Optional[str] = None
    assigned_to: Optional[str] = None
    transitioned_at: datetime


class DocumentWorkflowState(BaseModel):
    """Minimal document summary with current workflow status."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    filename: str
    file_type: str
    status: str
    classification: Optional[str] = None
    assigned_reviewer: Optional[str] = None
    upload_timestamp: datetime


class SubmitRequest(BaseModel):
    """Body for POST /api/documents/{id}/submit."""
    comment: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional message from the submitter to the reviewer.",
    )


class AssignRequest(BaseModel):
    """Body for POST /api/documents/{id}/assign."""
    assigned_to: str = Field(
        ...,
        description="User ID of the reviewer being assigned.",
    )
    comment: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional routing note.",
    )


class RequestChangesRequest(BaseModel):
    """Body for POST /api/documents/{id}/request-changes."""
    comment: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Mandatory explanation of what needs to change.",
    )


class ResubmitRequest(BaseModel):
    """Body for POST /api/documents/{id}/resubmit."""
    comment: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional note describing what was changed.",
    )


class DecisionRequest(BaseModel):
    """Body for POST /api/documents/{id}/approve or /reject."""
    comment: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Reason or notes for this decision.",
    )
