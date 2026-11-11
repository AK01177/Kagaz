"""
BE-10: Document Workflow State Machine API routes.
BE-11: Review and Approval API routes.

All endpoints that change workflow state are protected by the appropriate role
dependencies. AI validation findings are informational only — they do not
automatically approve or reject documents.

Routes
------
POST /api/documents/{id}/submit            Submitter -> PENDING_REVIEW
POST /api/documents/{id}/assign            Reviewer/Admin -> UNDER_REVIEW
POST /api/documents/{id}/request-changes   Reviewer -> CHANGES_REQUESTED
POST /api/documents/{id}/resubmit          Submitter -> PENDING_REVIEW
POST /api/documents/{id}/approve           Approver -> APPROVED
POST /api/documents/{id}/reject            Approver -> REJECTED
GET  /api/review/queue                     Returns permitted review queue
GET  /api/documents/{id}/workflow-history  Returns full transition history
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import require_reviewer, require_submitter
from app.db.session import get_db
from app.models.workflow import WorkflowAction
from app.schemas.workflow import (
    AssignRequest,
    DecisionRequest,
    DocumentWorkflowState,
    RequestChangesRequest,
    ResubmitRequest,
    SubmitRequest,
    WorkflowTransitionResponse,
)
from services.workflow import apply_transition, get_review_queue, get_transition_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["workflow"])


# ---------------------------------------------------------------------------
# Helper: role guard for reviewer-or-higher
# ---------------------------------------------------------------------------

_REVIEWER_OR_HIGHER = {"REVIEWER", "APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"}
_APPROVER_OR_HIGHER = {"APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"}


def _require_active_db(db: Session | None) -> Session:
    if db is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "DATABASE_UNAVAILABLE", "message": "Workflow service requires the database."},
        )
    return db


# ---------------------------------------------------------------------------
# BE-10: State machine action endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/documents/{document_id}/submit",
    response_model=WorkflowTransitionResponse,
    summary="Submit a document for review",
)
def submit_document(
    document_id: str,
    body: SubmitRequest,
    identity: dict = Depends(require_submitter),
    db: Session | None = Depends(get_db),
):
    """
    Submitter transitions a CLASSIFIED document to PENDING_REVIEW.

    The document must be CLASSIFIED before it can be submitted.
    AI validation findings do not block this action.
    """
    db = _require_active_db(db)
    result = apply_transition(
        db,
        document_id,
        WorkflowAction.SUBMIT,
        identity,
        comment=body.comment,
    )
    logger.info(
        "workflow action=SUBMIT document=%s actor=%s org=%s",
        document_id,
        identity["sub"],
        identity["organization_id"],
    )
    return result.transition


@router.post(
    "/documents/{document_id}/assign",
    response_model=WorkflowTransitionResponse,
    summary="Assign a reviewer to a document",
)
def assign_reviewer(
    document_id: str,
    body: AssignRequest,
    identity: dict = Depends(require_reviewer),
    db: Session | None = Depends(get_db),
):
    """
    Reviewer or admin routes a PENDING_REVIEW document to a specific reviewer.

    Requires REVIEWER, APPROVER, or ORG_ADMIN role. The `assigned_to` field
    must be the user ID of an eligible reviewer in the same organization.
    """
    db = _require_active_db(db)
    if identity.get("role") not in _REVIEWER_OR_HIGHER:
        raise HTTPException(
            status_code=403,
            detail={"code": "ASSIGN_FORBIDDEN", "message": "Reviewer or higher role required."},
        )
    result = apply_transition(
        db,
        document_id,
        WorkflowAction.ASSIGN,
        identity,
        comment=body.comment,
        assigned_to=body.assigned_to,
    )
    logger.info(
        "workflow action=ASSIGN document=%s actor=%s assigned_to=%s org=%s",
        document_id,
        identity["sub"],
        body.assigned_to,
        identity["organization_id"],
    )
    return result.transition


@router.post(
    "/documents/{document_id}/request-changes",
    response_model=WorkflowTransitionResponse,
    summary="Request changes on a document under review",
)
def request_changes(
    document_id: str,
    body: RequestChangesRequest,
    identity: dict = Depends(require_reviewer),
    db: Session | None = Depends(get_db),
):
    """
    Reviewer sends the document back to the submitter with mandatory feedback.

    A non-empty comment is required; the endpoint returns 422 without it.
    """
    db = _require_active_db(db)
    result = apply_transition(
        db,
        document_id,
        WorkflowAction.REQUEST_CHANGES,
        identity,
        comment=body.comment,
    )
    logger.info(
        "workflow action=REQUEST_CHANGES document=%s actor=%s org=%s",
        document_id,
        identity["sub"],
        identity["organization_id"],
    )
    return result.transition


@router.post(
    "/documents/{document_id}/resubmit",
    response_model=WorkflowTransitionResponse,
    summary="Resubmit a document after changes were requested",
)
def resubmit_document(
    document_id: str,
    body: ResubmitRequest,
    identity: dict = Depends(require_submitter),
    db: Session | None = Depends(get_db),
):
    """
    Submitter addresses reviewer feedback and re-submits the document.

    Preserves the full transition history so reviewers can see all previous rounds.
    """
    db = _require_active_db(db)
    result = apply_transition(
        db,
        document_id,
        WorkflowAction.RESUBMIT,
        identity,
        comment=body.comment,
    )
    logger.info(
        "workflow action=RESUBMIT document=%s actor=%s org=%s",
        document_id,
        identity["sub"],
        identity["organization_id"],
    )
    return result.transition


# ---------------------------------------------------------------------------
# BE-11: Review and Approval endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/documents/{document_id}/approve",
    response_model=WorkflowTransitionResponse,
    summary="Approve a document",
)
def approve_document(
    document_id: str,
    body: DecisionRequest,
    identity: dict = Depends(require_reviewer),
    db: Session | None = Depends(get_db),
):
    """
    Approver makes a final approval decision.

    Only APPROVER, ORG_ADMIN, or SYSTEM_ADMIN can approve. The document must
    be in PENDING_REVIEW or UNDER_REVIEW status. APPROVED is a terminal state.
    """
    db = _require_active_db(db)
    if identity.get("role") not in _APPROVER_OR_HIGHER:
        raise HTTPException(
            status_code=403,
            detail={"code": "APPROVE_FORBIDDEN", "message": "Approver or admin role required to approve."},
        )
    result = apply_transition(
        db,
        document_id,
        WorkflowAction.APPROVE,
        identity,
        comment=body.comment,
    )
    logger.info(
        "workflow action=APPROVE document=%s actor=%s org=%s",
        document_id,
        identity["sub"],
        identity["organization_id"],
    )
    return result.transition


@router.post(
    "/documents/{document_id}/reject",
    response_model=WorkflowTransitionResponse,
    summary="Reject a document",
)
def reject_document(
    document_id: str,
    body: DecisionRequest,
    identity: dict = Depends(require_reviewer),
    db: Session | None = Depends(get_db),
):
    """
    Approver makes a final rejection decision.

    Only APPROVER, ORG_ADMIN, or SYSTEM_ADMIN can reject. The document must
    be in PENDING_REVIEW or UNDER_REVIEW status. REJECTED is a terminal state.
    """
    db = _require_active_db(db)
    if identity.get("role") not in _APPROVER_OR_HIGHER:
        raise HTTPException(
            status_code=403,
            detail={"code": "REJECT_FORBIDDEN", "message": "Approver or admin role required to reject."},
        )
    result = apply_transition(
        db,
        document_id,
        WorkflowAction.REJECT,
        identity,
        comment=body.comment,
    )
    logger.info(
        "workflow action=REJECT document=%s actor=%s org=%s",
        document_id,
        identity["sub"],
        identity["organization_id"],
    )
    return result.transition


# ---------------------------------------------------------------------------
# BE-11: Review queue
# ---------------------------------------------------------------------------


@router.get(
    "/review/queue",
    response_model=list[DocumentWorkflowState],
    summary="Retrieve the permitted review queue for the caller",
)
def review_queue(
    identity: dict = Depends(require_reviewer),
    db: Session | None = Depends(get_db),
):
    """
    Return documents the caller is eligible to act on.

    * REVIEWER: only documents assigned to them.
    * APPROVER / ORG_ADMIN: all PENDING_REVIEW and UNDER_REVIEW documents
      in their organization.

    Documents from other organizations are never included.
    """
    db = _require_active_db(db)
    return get_review_queue(db, identity)


# ---------------------------------------------------------------------------
# BE-11 / BE-12: Workflow history
# ---------------------------------------------------------------------------


@router.get(
    "/documents/{document_id}/workflow-history",
    response_model=list[WorkflowTransitionResponse],
    summary="Retrieve the full workflow transition history for a document",
)
def workflow_history(
    document_id: str,
    identity: dict = Depends(require_reviewer),
    db: Session | None = Depends(get_db),
):
    """
    Return every WorkflowTransition for the document in chronological order.

    Requires at least REVIEWER role. Organization scoping is enforced: a
    document from a different org always returns 404.
    """
    db = _require_active_db(db)
    return get_transition_history(db, document_id, identity["organization_id"])
