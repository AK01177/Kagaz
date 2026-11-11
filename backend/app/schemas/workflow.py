"""
Pydantic schemas for document workflow lifecycle transitions and reviewer assignment.
"""
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus
from app.models.workflow import WorkflowAction


class SubmitDocumentRequest(BaseModel):
    reviewer_id: Optional[str] = None
    auto_route: bool = False
    comment: Optional[str] = None


class AssignReviewerRequest(BaseModel):
    reviewer_id: Optional[str] = None
    auto_route: bool = False
    comment: Optional[str] = None


class RequestChangesRequest(BaseModel):
    comment: Optional[str] = None


class ResubmitDocumentRequest(BaseModel):
    reviewer_id: Optional[str] = None
    auto_route: bool = False
    comment: Optional[str] = None


class SubmitForApprovalRequest(BaseModel):
    approver_id: Optional[str] = None
    auto_route: bool = False
    comment: Optional[str] = None


class DecisionRequest(BaseModel):
    comment: Optional[str] = None


class DocumentTransitionResponse(BaseModel):
    id: str
    document_id: str
    organization_id: str
    action: WorkflowAction
    from_status: str
    to_status: str
    actor_id: str
    actor_role: str
    assigned_to_id: Optional[str] = None
    previous_assignee_id: Optional[str] = None
    comment: Optional[str] = None
    revision_number: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ValidationSummaryResponse(BaseModel):
    """Advisory AI/policy validation summary kept separate from workflow status."""

    status: Optional[str] = None
    policy_version: Optional[str] = None
    issues: List[Any] = Field(default_factory=list)
    latest_policy_run_status: Optional[str] = None


class EligibleReviewerResponse(BaseModel):
    user_id: str
    email: str
    full_name: Optional[str] = None
    role: str


class DocumentWorkflowResponse(BaseModel):
    document_id: str
    organization_id: str
    status: DocumentStatus
    assigned_reviewer_id: Optional[str] = None
    assigned_approver_id: Optional[str] = None
    revision_number: int
    workflow_updated_at: Optional[datetime] = None
    last_decision_by: Optional[str] = None
    last_decision_comment: Optional[str] = None
    last_transition: Optional[DocumentTransitionResponse] = None
    history: List[DocumentTransitionResponse] = Field(default_factory=list)
    validation_summary: Optional[ValidationSummaryResponse] = None
