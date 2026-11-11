"""API routes for document workflow lifecycle transitions and reviewer assignment."""
from __future__ import annotations

from typing import Annotated, Callable, List, Optional, TypeVar

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.auth import Permission, require_audit_reader, require_permission
from app.db.session import get_db
from app.schemas.workflow import (
    AssignReviewerRequest,
    DecisionRequest,
    DocumentAuditTrailResponse,
    DocumentReviewDetailResponse,
    DocumentWorkflowResponse,
    EligibleReviewerResponse,
    RequestChangesRequest,
    ResubmitDocumentRequest,
    ReviewCommentRequest,
    ReviewCommentResponse,
    ReviewQueueResponse,
    SubmitDocumentRequest,
    SubmitForApprovalRequest,
)
from services.workflow import (
    WorkflowError,
    add_review_comment,
    assign_reviewer,
    decide_document,
    get_approval_queue,
    get_document_audit_trail,
    get_document_review_detail,
    get_document_workflow,
    get_review_queue,
    list_eligible_reviewers,
    request_changes,
    resubmit_document,
    submit_document,
    submit_for_approval,
)

router = APIRouter(prefix="/api/documents", tags=["workflow"])
audit_router = APIRouter(prefix="/api/audit", tags=["audit"])
_T = TypeVar("_T")


def _require_db(db: Optional[Session]) -> Session:
    if db is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "DATABASE_UNAVAILABLE",
                "message": "Database connection is required for workflow operations.",
            },
        )
    return db


def _run_workflow_action(fn: Callable[[], _T]) -> _T:
    try:
        return fn()
    except WorkflowError as exc:
        detail = {"code": exc.code, "message": exc.message}
        if exc.details:
            detail["details"] = exc.details
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


@router.get("/workflow/review-queue", response_model=ReviewQueueResponse)
def get_review_queue_endpoint(
    actor: Annotated[dict, Depends(require_permission(Permission.WORKFLOW_REVIEW_QUEUE))],
    status: Optional[str] = Query(default=None),
    assigned_to_me: bool = Query(default=False),
    classification: Optional[str] = Query(default=None),
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> ReviewQueueResponse:
    """Return documents in the caller's organization that the caller is permitted to review."""
    session = _require_db(db)
    return _run_workflow_action(
        lambda: get_review_queue(
            session,
            actor,
            status_filter=status,
            assigned_to_me=assigned_to_me,
            classification=classification,
        )
    )


@router.get("/workflow/approval-queue", response_model=ReviewQueueResponse)
def get_approval_queue_endpoint(
    actor: Annotated[dict, Depends(require_permission(Permission.WORKFLOW_APPROVAL_QUEUE))],
    assigned_to_me: bool = Query(default=False),
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> ReviewQueueResponse:
    """Return documents eligible for human approval within the caller's organization."""
    session = _require_db(db)
    return _run_workflow_action(
        lambda: get_approval_queue(session, actor, assigned_to_me=assigned_to_me)
    )


@router.get("/workflow/reviewers", response_model=List[EligibleReviewerResponse])
def list_workflow_reviewers_endpoint(
    actor: Annotated[dict, Depends(require_permission(Permission.WORKFLOW_VIEW_REVIEWERS))],
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> List[EligibleReviewerResponse]:
    """List active users eligible to review documents in the caller's organization."""
    session = _require_db(db)
    return list_eligible_reviewers(session, str(actor["organization_id"]))


@router.get("/{document_id}/workflow", response_model=DocumentWorkflowResponse)
def get_document_workflow_endpoint(
    document_id: str,
    actor: Annotated[dict, Depends(require_permission(Permission.WORKFLOW_VIEW_STATUS))],
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> DocumentWorkflowResponse:
    """Return current document workflow state, assignees, transition history, and advisory validation."""
    session = _require_db(db)
    return _run_workflow_action(lambda: get_document_workflow(session, document_id, actor))


@router.post("/{document_id}/submit", response_model=DocumentWorkflowResponse)
def submit_document_endpoint(
    document_id: str,
    actor: Annotated[dict, Depends(require_permission(Permission.WORKFLOW_SUBMIT))],
    payload: Optional[SubmitDocumentRequest] = Body(default=None),
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> DocumentWorkflowResponse:
    """Submit a completed document for review and optionally assign or route to a reviewer."""
    session = _require_db(db)
    req = payload or SubmitDocumentRequest()
    return _run_workflow_action(
        lambda: submit_document(
            session,
            document_id,
            actor,
            reviewer_id=req.reviewer_id,
            auto_route=req.auto_route,
            comment=req.comment,
        )
    )


@router.post("/{document_id}/assign", response_model=DocumentWorkflowResponse)
def assign_reviewer_endpoint(
    document_id: str,
    actor: Annotated[dict, Depends(require_permission(Permission.WORKFLOW_ASSIGN_REVIEWER))],
    payload: AssignReviewerRequest = Body(...),
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> DocumentWorkflowResponse:
    """Assign or reassign a submitted/in-review document to an eligible active reviewer."""
    session = _require_db(db)
    return _run_workflow_action(
        lambda: assign_reviewer(
            session,
            document_id,
            actor,
            reviewer_id=payload.reviewer_id,
            auto_route=payload.auto_route,
            comment=payload.comment,
        )
    )


@router.post("/{document_id}/request-changes", response_model=DocumentWorkflowResponse)
def request_changes_endpoint(
    document_id: str,
    actor: Annotated[dict, Depends(require_permission(Permission.WORKFLOW_REQUEST_CHANGES))],
    payload: Optional[RequestChangesRequest] = Body(default=None),
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> DocumentWorkflowResponse:
    """Return a document for changes with a mandatory non-empty comment."""
    session = _require_db(db)
    req = payload or RequestChangesRequest()
    return _run_workflow_action(
        lambda: request_changes(
            session,
            document_id,
            actor,
            comment=req.comment,
        )
    )


@router.post("/{document_id}/resubmit", response_model=DocumentWorkflowResponse)
def resubmit_document_endpoint(
    document_id: str,
    actor: Annotated[dict, Depends(require_permission(Permission.WORKFLOW_RESUBMIT))],
    payload: Optional[ResubmitDocumentRequest] = Body(default=None),
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> DocumentWorkflowResponse:
    """Resubmit a CHANGES_REQUESTED document while preserving full transition history."""
    session = _require_db(db)
    req = payload or ResubmitDocumentRequest()
    return _run_workflow_action(
        lambda: resubmit_document(
            session,
            document_id,
            actor,
            reviewer_id=req.reviewer_id,
            auto_route=req.auto_route,
            comment=req.comment,
        )
    )


@router.post("/{document_id}/submit-for-approval", response_model=DocumentWorkflowResponse)
def submit_for_approval_endpoint(
    document_id: str,
    actor: Annotated[dict, Depends(require_permission(Permission.WORKFLOW_SUBMIT_FOR_APPROVAL))],
    payload: Optional[SubmitForApprovalRequest] = Body(default=None),
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> DocumentWorkflowResponse:
    """Advance an IN_REVIEW document to PENDING_APPROVAL and optionally route to an approver."""
    session = _require_db(db)
    req = payload or SubmitForApprovalRequest()
    return _run_workflow_action(
        lambda: submit_for_approval(
            session,
            document_id,
            actor,
            approver_id=req.approver_id,
            auto_route=req.auto_route,
            comment=req.comment,
        )
    )


@router.get("/{document_id}/review", response_model=DocumentReviewDetailResponse)
def get_document_review_detail_endpoint(
    document_id: str,
    actor: Annotated[dict, Depends(require_permission(Permission.WORKFLOW_REVIEW_DETAIL))],
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> DocumentReviewDetailResponse:
    """Return permitted document details, extractions, validation evidence, comments, and audit events."""
    session = _require_db(db)
    return _run_workflow_action(lambda: get_document_review_detail(session, document_id, actor))


@router.post("/{document_id}/comments", response_model=ReviewCommentResponse, status_code=201)
def add_review_comment_endpoint(
    document_id: str,
    actor: Annotated[dict, Depends(require_permission(Permission.WORKFLOW_REVIEW_COMMENT))],
    payload: Optional[ReviewCommentRequest] = Body(default=None),
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> ReviewCommentResponse:
    """Submit a review comment and record an audit event."""
    session = _require_db(db)
    req = payload or ReviewCommentRequest()
    return _run_workflow_action(
        lambda: add_review_comment(session, document_id, actor, comment=req.comment)
    )


@router.post("/{document_id}/approve", response_model=DocumentWorkflowResponse)
def approve_document_endpoint(
    document_id: str,
    actor: Annotated[dict, Depends(require_permission(Permission.WORKFLOW_DECIDE))],
    payload: Optional[DecisionRequest] = Body(default=None),
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> DocumentWorkflowResponse:
    """Record an explicit human approval decision from an authorized approver."""
    session = _require_db(db)
    req = payload or DecisionRequest()
    return _run_workflow_action(
        lambda: decide_document(
            session,
            document_id,
            actor,
            approve=True,
            reason=req.reason,
            comment=req.comment,
        )
    )


@router.post("/{document_id}/reject", response_model=DocumentWorkflowResponse)
def reject_document_endpoint(
    document_id: str,
    actor: Annotated[dict, Depends(require_permission(Permission.WORKFLOW_DECIDE))],
    payload: Optional[DecisionRequest] = Body(default=None),
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> DocumentWorkflowResponse:
    """Record an explicit human rejection decision from an authorized approver."""
    session = _require_db(db)
    req = payload or DecisionRequest()
    return _run_workflow_action(
        lambda: decide_document(
            session,
            document_id,
            actor,
            approve=False,
            reason=req.reason,
            comment=req.comment,
        )
    )


@audit_router.get("/{document_id}", response_model=DocumentAuditTrailResponse)
def get_document_audit_trail_endpoint(
    document_id: str,
    actor: Annotated[dict, Depends(require_audit_reader)],
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> DocumentAuditTrailResponse:
    """Return chronological audit trail events for a permitted document."""
    session = _require_db(db)
    return _run_workflow_action(lambda: get_document_audit_trail(session, document_id, actor))
