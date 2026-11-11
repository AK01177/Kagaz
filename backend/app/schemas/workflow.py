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
    reason: Optional[str] = None
    comment: Optional[str] = None


class ReviewCommentRequest(BaseModel):
    comment: Optional[str] = None


class ReviewCommentResponse(BaseModel):
    id: str
    document_id: str
    organization_id: str
    author_id: str
    author_role: str
    comment: str
    revision_number: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditEventResponse(BaseModel):
    id: str
    document_id: str
    organization_id: str
    event_type: str
    actor_id: str
    actor_type: str = "USER"
    actor_role: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    decision: Optional[str] = None
    reason: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)
    sequence_no: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentAuditTrailResponse(BaseModel):
    document_id: str
    organization_id: str
    status: DocumentStatus
    events: List[AuditEventResponse] = Field(default_factory=list)


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
    last_decision_at: Optional[datetime] = None
    last_decision_comment: Optional[str] = None
    decision: Optional[str] = None
    comment: Optional[str] = None
    last_transition: Optional[DocumentTransitionResponse] = None
    audit_event: Optional[AuditEventResponse] = None
    history: List[DocumentTransitionResponse] = Field(default_factory=list)
    validation_summary: Optional[ValidationSummaryResponse] = None


class QueueDocumentItemResponse(BaseModel):
    document_id: str
    organization_id: str
    uploaded_by: str
    filename: str
    file_type: str
    file_size: int
    status: DocumentStatus
    classification: Optional[str] = None
    classification_confidence: Optional[float] = None
    assigned_reviewer_id: Optional[str] = None
    assigned_approver_id: Optional[str] = None
    revision_number: int
    upload_timestamp: datetime
    workflow_updated_at: Optional[datetime] = None
    last_decision_by: Optional[str] = None
    last_decision_at: Optional[datetime] = None
    last_decision_comment: Optional[str] = None


class ReviewQueueResponse(BaseModel):
    items: List[QueueDocumentItemResponse] = Field(default_factory=list)
    total: int


class ReviewExtractionItemResponse(BaseModel):
    field_name: str
    value: str
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewValidationEvidenceResponse(BaseModel):
    status: str
    policy_id: Optional[str] = None
    policy_version: Optional[str] = None
    issues: List[Any] = Field(default_factory=list)
    evidence: List[Any] = Field(default_factory=list)
    validated_by: Optional[str] = None
    validated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewPolicyFindingResponse(BaseModel):
    id: str
    status: str
    requirement: str
    explanation: str
    field_name: Optional[str] = None
    document_value: Optional[str] = None
    confidence: Optional[float] = None
    source_references: List[Any] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ReviewPolicyValidationRunResponse(BaseModel):
    id: str
    status: str
    summary: str
    retrieval_outcome: str
    policy_versions: List[Any] = Field(default_factory=list)
    requested_by: str
    created_at: datetime
    findings: List[ReviewPolicyFindingResponse] = Field(default_factory=list)


class DocumentReviewDetailResponse(BaseModel):
    document: QueueDocumentItemResponse
    extractions: List[ReviewExtractionItemResponse] = Field(default_factory=list)
    ocr_text: Optional[str] = None
    validation: Optional[ReviewValidationEvidenceResponse] = None
    policy_validation_runs: List[ReviewPolicyValidationRunResponse] = Field(default_factory=list)
    comments: List[ReviewCommentResponse] = Field(default_factory=list)
    history: List[DocumentTransitionResponse] = Field(default_factory=list)
    audit_events: List[AuditEventResponse] = Field(default_factory=list)
