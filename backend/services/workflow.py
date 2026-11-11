"""
BE-10: Document Workflow State Machine Service.

Enforces valid document lifecycle transitions, validates actor eligibility,
persists WorkflowTransition records, and updates Document.status atomically.

Transition matrix
-----------------
CLASSIFIED         -> PENDING_REVIEW  (SUBMIT,          SUBMITTER)
CHANGES_REQUESTED  -> PENDING_REVIEW  (RESUBMIT,        SUBMITTER)
PENDING_REVIEW     -> UNDER_REVIEW    (ASSIGN,           REVIEWER / ORG_ADMIN)
UNDER_REVIEW       -> CHANGES_REQUESTED (REQUEST_CHANGES, REVIEWER)
UNDER_REVIEW       -> PENDING_REVIEW  (ASSIGN,           ORG_ADMIN — re-route)
PENDING_REVIEW     -> APPROVED        (APPROVE,          APPROVER / ORG_ADMIN)
PENDING_REVIEW     -> REJECTED        (REJECT,           APPROVER / ORG_ADMIN)
UNDER_REVIEW       -> APPROVED        (APPROVE,          APPROVER / ORG_ADMIN)
UNDER_REVIEW       -> REJECTED        (REJECT,           APPROVER / ORG_ADMIN)

Design notes
------------
* AI validation findings (PolicyValidationRun) inform reviewers but do NOT
  automatically approve or reject — BE-10 acceptance criterion.
* Every successful transition produces a WorkflowTransition record (append-only).
* The Document.status column is updated in the same transaction.
* Callers must supply the SQLAlchemy Session; this module has no HTTP layer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.models.workflow import WorkflowAction, WorkflowTransition

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Transition matrix
# ---------------------------------------------------------------------------

# Maps (from_status, action) -> (to_status, permitted_roles)
_TRANSITIONS: dict[
    tuple[DocumentStatus, WorkflowAction],
    tuple[DocumentStatus, frozenset[str]],
] = {
    # Submitter submits a classified document for review
    (DocumentStatus.CLASSIFIED, WorkflowAction.SUBMIT): (
        DocumentStatus.PENDING_REVIEW,
        frozenset({"SUBMITTER"}),
    ),
    # Submitter resubmits after reviewer requested changes
    (DocumentStatus.CHANGES_REQUESTED, WorkflowAction.RESUBMIT): (
        DocumentStatus.PENDING_REVIEW,
        frozenset({"SUBMITTER"}),
    ),
    # Reviewer / admin assigns a reviewer to the document
    (DocumentStatus.PENDING_REVIEW, WorkflowAction.ASSIGN): (
        DocumentStatus.UNDER_REVIEW,
        frozenset({"REVIEWER", "ORG_ADMIN", "SYSTEM_ADMIN"}),
    ),
    # Admin re-routes an already-assigned document
    (DocumentStatus.UNDER_REVIEW, WorkflowAction.ASSIGN): (
        DocumentStatus.UNDER_REVIEW,
        frozenset({"ORG_ADMIN", "SYSTEM_ADMIN"}),
    ),
    # Reviewer sends back for changes (comment required)
    (DocumentStatus.UNDER_REVIEW, WorkflowAction.REQUEST_CHANGES): (
        DocumentStatus.CHANGES_REQUESTED,
        frozenset({"REVIEWER", "ORG_ADMIN", "SYSTEM_ADMIN"}),
    ),
    # Approver / admin approves from PENDING_REVIEW
    (DocumentStatus.PENDING_REVIEW, WorkflowAction.APPROVE): (
        DocumentStatus.APPROVED,
        frozenset({"APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"}),
    ),
    # Approver / admin rejects from PENDING_REVIEW
    (DocumentStatus.PENDING_REVIEW, WorkflowAction.REJECT): (
        DocumentStatus.REJECTED,
        frozenset({"APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"}),
    ),
    # Approver / admin approves from UNDER_REVIEW
    (DocumentStatus.UNDER_REVIEW, WorkflowAction.APPROVE): (
        DocumentStatus.APPROVED,
        frozenset({"APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"}),
    ),
    # Approver / admin rejects from UNDER_REVIEW
    (DocumentStatus.UNDER_REVIEW, WorkflowAction.REJECT): (
        DocumentStatus.REJECTED,
        frozenset({"APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"}),
    ),
}

# Terminal states that cannot be transitioned away from
_TERMINAL_STATES: frozenset[DocumentStatus] = frozenset(
    {DocumentStatus.APPROVED, DocumentStatus.REJECTED}
)


@dataclass
class TransitionResult:
    """Returned by apply_transition on success."""
    document: Document
    transition: WorkflowTransition


def _get_document_in_org(db: Session, document_id: str, organization_id: str) -> Document:
    """Load a document, enforcing org-scope isolation."""
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
        .first()
    )
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": "Document not found."},
        )
    return doc


def apply_transition(
    db: Session,
    document_id: str,
    action: WorkflowAction,
    identity: dict,
    *,
    comment: Optional[str] = None,
    assigned_to: Optional[str] = None,
) -> TransitionResult:
    """
    Apply a workflow action to a document, enforcing all state-machine rules.

    Parameters
    ----------
    db            Active SQLAlchemy session.
    document_id   The target document's string ID.
    action        The WorkflowAction being requested.
    identity      Decoded JWT claims dict (sub, role, organization_id, active).
    comment       Free-text comment; required for REQUEST_CHANGES.
    assigned_to   Target user ID; required for ASSIGN.

    Returns
    -------
    TransitionResult with the updated Document and the new WorkflowTransition.

    Raises
    ------
    HTTPException 403  Role not permitted for this transition.
    HTTPException 404  Document not found (or not in caller's org).
    HTTPException 409  Invalid transition from the current state.
    HTTPException 422  Missing required comment or assignment target.
    """
    actor_role: str = identity.get("role", "")
    actor_id: str = identity.get("sub", "")
    org_id: str = identity.get("organization_id", "")

    doc = _get_document_in_org(db, document_id, org_id)
    current_status = doc.status

    # Terminal state guard
    if current_status in _TERMINAL_STATES:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DOCUMENT_IN_TERMINAL_STATE",
                "message": f"Document is in a terminal state ({current_status.value}) and cannot be transitioned.",
            },
        )

    transition_key = (current_status, action)
    allowed = _TRANSITIONS.get(transition_key)
    if allowed is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INVALID_WORKFLOW_TRANSITION",
                "message": (
                    f"Action '{action.value}' is not permitted when the document "
                    f"status is '{current_status.value}'."
                ),
            },
        )

    to_status, permitted_roles = allowed

    if actor_role not in permitted_roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "WORKFLOW_FORBIDDEN",
                "message": (
                    f"Role '{actor_role}' cannot perform action '{action.value}' "
                    f"from status '{current_status.value}'."
                ),
            },
        )

    # Validate action-specific requirements
    if action == WorkflowAction.REQUEST_CHANGES:
        if not comment or not comment.strip():
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "COMMENT_REQUIRED",
                    "message": "A comment is required when requesting changes.",
                },
            )

    if action == WorkflowAction.ASSIGN:
        if not assigned_to or not assigned_to.strip():
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "ASSIGNEE_REQUIRED",
                    "message": "An assignee user ID is required for the ASSIGN action.",
                },
            )

    # Persist the transition and update document status atomically
    record = WorkflowTransition(
        document_id=doc.id,
        organization_id=org_id,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        from_status=current_status.value,
        to_status=to_status.value,
        comment=comment.strip() if comment else None,
        assigned_to=assigned_to.strip() if assigned_to else None,
    )

    doc.status = to_status
    if action == WorkflowAction.ASSIGN:
        doc.assigned_reviewer = assigned_to.strip()
    elif to_status in _TERMINAL_STATES:
        # Clear the reviewer assignment when the document is finalized
        doc.assigned_reviewer = None

    db.add(record)
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to persist workflow transition for document %s", document_id
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "WORKFLOW_TRANSITION_FAILED",
                "message": "The workflow transition could not be saved.",
            },
        )

    db.refresh(doc)
    db.refresh(record)
    return TransitionResult(document=doc, transition=record)


def get_transition_history(
    db: Session,
    document_id: str,
    organization_id: str,
) -> list[WorkflowTransition]:
    """
    Return the full, chronologically ordered transition history for a document.

    Enforces organization scoping: documents from other orgs raise 404.
    """
    # Verify the document belongs to the org before exposing history
    _get_document_in_org(db, document_id, organization_id)
    return (
        db.query(WorkflowTransition)
        .filter(WorkflowTransition.document_id == document_id)
        .order_by(WorkflowTransition.transitioned_at.asc())
        .all()
    )


def get_review_queue(
    db: Session,
    identity: dict,
) -> list[Document]:
    """
    Return documents the caller is eligible to review.

    * REVIEWER / AUDITOR / COMPLIANCE: documents assigned to them.
    * APPROVER / ORG_ADMIN / SYSTEM_ADMIN: all PENDING_REVIEW or UNDER_REVIEW
      documents in their organization.
    """
    org_id = identity["organization_id"]
    role = identity["role"]
    actor_id = identity["sub"]

    if role in {"APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"}:
        return (
            db.query(Document)
            .filter(
                Document.organization_id == org_id,
                Document.status.in_(
                    [DocumentStatus.PENDING_REVIEW, DocumentStatus.UNDER_REVIEW]
                ),
            )
            .order_by(Document.upload_timestamp.asc())
            .all()
        )

    # Reviewer: only their assigned documents
    return (
        db.query(Document)
        .filter(
            Document.organization_id == org_id,
            Document.assigned_reviewer == actor_id,
            Document.status.in_(
                [DocumentStatus.PENDING_REVIEW, DocumentStatus.UNDER_REVIEW]
            ),
        )
        .order_by(Document.upload_timestamp.asc())
        .all()
    )
