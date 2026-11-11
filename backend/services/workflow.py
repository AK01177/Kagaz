"""
Document workflow state machine and reviewer/approver assignment engine.

Enforces valid lifecycle transitions, RBAC actor permissions, organization-scoped
reviewer/approver eligibility, required comments on change requests, strict
separation from AI/policy validation findings, and transactional persistence of
state changes alongside append-only transition history.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.models.extraction import Extraction
from app.models.membership import Membership, MembershipRole
from app.models.policy_validation import PolicyValidationRun
from app.models.user import User
from app.models.validation import ValidationResult
from app.models.workflow import AuditEvent, DocumentTransition, ReviewComment, WorkflowAction
from services.audit import build_audit_event, sanitize_audit_text
from app.schemas.workflow import (
    AuditEventResponse,
    DocumentAuditTrailResponse,
    DocumentReviewDetailResponse,
    DocumentTransitionResponse,
    DocumentWorkflowResponse,
    EligibleReviewerResponse,
    QueueDocumentItemResponse,
    ReviewCommentResponse,
    ReviewExtractionItemResponse,
    ReviewPolicyFindingResponse,
    ReviewPolicyValidationRunResponse,
    ReviewQueueResponse,
    ReviewValidationEvidenceResponse,
    ValidationSummaryResponse,
)
from storage.document_storage import DocumentStorage

logger = logging.getLogger(__name__)


class WorkflowError(Exception):
    """Structured workflow domain exception translated to consistent API errors."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


COMPLETED_PRE_REVIEW_STATUSES = {
    DocumentStatus.CLASSIFIED,
    DocumentStatus.EXTRACTED,
    DocumentStatus.VALIDATED,
    DocumentStatus.REVIEW_REQUIRED,
}
ASSIGN_REVIEWER_ALLOWED_FROM = {
    DocumentStatus.SUBMITTED,
    DocumentStatus.IN_REVIEW,
}
REQUEST_CHANGES_ALLOWED_FROM = {
    DocumentStatus.IN_REVIEW,
    DocumentStatus.PENDING_APPROVAL,
}
RESUBMIT_ALLOWED_FROM = {
    DocumentStatus.CHANGES_REQUESTED,
}
SUBMIT_FOR_APPROVAL_ALLOWED_FROM = {
    DocumentStatus.IN_REVIEW,
}
DECISION_ALLOWED_FROM = {
    DocumentStatus.IN_REVIEW,
    DocumentStatus.PENDING_APPROVAL,
}

SUBMIT_CALLER_ROLES = {"SUBMITTER", "ORG_ADMIN", "SYSTEM_ADMIN"}
ASSIGN_REVIEWER_CALLER_ROLES = {"REVIEWER", "APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"}
REQUEST_CHANGES_REVIEWER_ROLES = {"REVIEWER", "APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"}
REQUEST_CHANGES_APPROVAL_ROLES = {"APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"}
SUBMIT_FOR_APPROVAL_CALLER_ROLES = {"REVIEWER", "ORG_ADMIN", "SYSTEM_ADMIN"}
APPROVER_CALLER_ROLES = {"APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"}
ADMIN_OVERRIDE_ROLES = {"ORG_ADMIN", "SYSTEM_ADMIN"}

ELIGIBLE_REVIEWER_ROLES = {
    MembershipRole.REVIEWER,
    MembershipRole.ORG_ADMIN,
    MembershipRole.SYSTEM_ADMIN,
}
ELIGIBLE_APPROVER_ROLES = {
    MembershipRole.APPROVER,
    MembershipRole.ORG_ADMIN,
    MembershipRole.SYSTEM_ADMIN,
}


REVIEW_QUEUE_CALLER_ROLES = {"REVIEWER", "APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"}
APPROVAL_QUEUE_CALLER_ROLES = {"APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"}
REVIEW_COMMENT_CALLER_ROLES = {"REVIEWER", "APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"}
REVIEW_COMMENT_ALLOWED_STATUSES = {
    DocumentStatus.SUBMITTED,
    DocumentStatus.IN_REVIEW,
    DocumentStatus.CHANGES_REQUESTED,
    DocumentStatus.PENDING_APPROVAL,
}
TERMINAL_DECISION_STATUSES = {
    DocumentStatus.APPROVED,
    DocumentStatus.REJECTED,
}
REVIEWER_QUEUE_STATUSES = {
    DocumentStatus.SUBMITTED,
    DocumentStatus.IN_REVIEW,
    DocumentStatus.CHANGES_REQUESTED,
}
APPROVER_QUEUE_STATUSES = {
    DocumentStatus.IN_REVIEW,
    DocumentStatus.PENDING_APPROVAL,
}

_ACTION_TO_EVENT_TYPE = {
    WorkflowAction.SUBMIT: "DOCUMENT_SUBMITTED",
    WorkflowAction.ASSIGN_REVIEWER: "REVIEWER_ASSIGNED",
    WorkflowAction.REASSIGN_REVIEWER: "REVIEWER_REASSIGNED",
    WorkflowAction.REQUEST_CHANGES: "CHANGES_REQUESTED",
    WorkflowAction.RESUBMIT: "DOCUMENT_RESUBMITTED",
    WorkflowAction.SUBMIT_FOR_APPROVAL: "SUBMITTED_FOR_APPROVAL",
    WorkflowAction.ASSIGN_APPROVER: "APPROVER_ASSIGNED",
    WorkflowAction.APPROVE: "DOCUMENT_APPROVED",
    WorkflowAction.REJECT: "DOCUMENT_REJECTED",
}
_DECISION_ACTIONS = {
    WorkflowAction.REQUEST_CHANGES: "CHANGES_REQUESTED",
    WorkflowAction.APPROVE: "APPROVED",
    WorkflowAction.REJECT: "REJECTED",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_comment(comment: Optional[str]) -> Optional[str]:
    if comment is None:
        return None
    stripped = comment.strip()
    return stripped or None


def _require_role(actor: dict, allowed_roles: set[str], action_label: str) -> tuple[str, str]:
    actor_id = str(actor.get("sub") or "").strip()
    actor_role = str(actor.get("role") or "").strip().upper()
    if not actor_id or not actor.get("active", False):
        raise WorkflowError(403, "WORKFLOW_FORBIDDEN", "An active authenticated account is required.")
    if actor_role not in allowed_roles:
        raise WorkflowError(
            403,
            "WORKFLOW_FORBIDDEN",
            f"Role '{actor_role or 'UNKNOWN'}' is not authorized to {action_label}.",
        )
    return actor_id, actor_role


def _get_scoped_document(db: Session, document_id: str, organization_id: str) -> Document:
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.organization_id == str(organization_id),
        )
        .first()
    )
    if document is None:
        raise WorkflowError(
            404,
            "DOCUMENT_NOT_FOUND",
            "Document was not found in your organization.",
        )
    return document


def _validate_invalid_transition(
    document: Document,
    allowed_from: set[DocumentStatus],
    action_label: str,
) -> None:
    if document.status not in allowed_from:
        allowed_values = sorted(status.value for status in allowed_from)
        details: dict[str, Any] = {
            "current_status": document.status.value,
            "allowed_statuses": allowed_values,
        }
        if document.status in TERMINAL_DECISION_STATUSES:
            details["duplicate_decision"] = True
            details["decision"] = document.status.value
        raise WorkflowError(
            409,
            "INVALID_STATE_TRANSITION",
            f"Cannot {action_label} document in status '{document.status.value}'. "
            f"Allowed statuses: {', '.join(allowed_values)}.",
            details=details,
        )


def _resolve_eligible_member(
    db: Session,
    organization_id: str,
    target_user_id: Optional[str],
    allowed_roles: set[MembershipRole],
    primary_role: MembershipRole,
    *,
    auto_route: bool = False,
    error_code: str = "INELIGIBLE_REVIEWER",
    no_candidate_code: str = "NO_ELIGIBLE_REVIEWER",
    role_label: str = "reviewer",
) -> Optional[str]:
    base_query = (
        db.query(Membership, User)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.organization_id == str(organization_id),
            Membership.is_active.is_(True),
            User.is_active.is_(True),
            Membership.role.in_(allowed_roles),
        )
    )

    if target_user_id is not None and target_user_id.strip():
        cleaned_id = target_user_id.strip()
        match = base_query.filter(User.id == cleaned_id).first()
        if match is None:
            raise WorkflowError(
                422,
                error_code,
                f"User '{cleaned_id}' is not an active eligible {role_label} in this organization.",
                details={"user_id": cleaned_id, "organization_id": str(organization_id)},
            )
        return cleaned_id

    if not auto_route:
        return None

    candidates = base_query.order_by(User.created_at.asc(), User.id.asc()).all()
    if not candidates:
        raise WorkflowError(
            422,
            no_candidate_code,
            f"No active eligible {role_label} is available in this organization.",
        )

    for membership, user in candidates:
        if membership.role == primary_role:
            return user.id
    return candidates[0][1].id


def _enforce_assignee_ownership(
    actor_id: str,
    actor_role: str,
    assigned_id: Optional[str],
    role_to_check: str,
    assignee_label: str,
) -> None:
    if (
        actor_role == role_to_check
        and actor_role not in ADMIN_OVERRIDE_ROLES
        and assigned_id
        and assigned_id != actor_id
    ):
        raise WorkflowError(
            403,
            "WORKFLOW_FORBIDDEN",
            f"Document is currently assigned to another {assignee_label}.",
        )


def _sync_sidecar_metadata(document: Document, storage: Optional[DocumentStorage] = None) -> None:
    """Mirror workflow status and assignees to local JSON metadata sidecar after DB commit."""
    try:
        doc_storage = storage or DocumentStorage()
        metadata_path = doc_storage.base_dir / "metadata" / f"{document.id}.json"
        if not metadata_path.exists():
            return
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        meta["status"] = document.status.value
        meta["assigned_reviewer_id"] = document.assigned_reviewer_id
        meta["assigned_approver_id"] = document.assigned_approver_id
        meta["revision_number"] = document.revision_number
        if document.workflow_updated_at is not None:
            meta["workflow_updated_at"] = document.workflow_updated_at.isoformat()
        metadata_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.debug("Non-fatal sidecar workflow sync failure for %s: %s", document.id, exc)


def _get_validation_summary(db: Session, document: Document) -> Optional[ValidationSummaryResponse]:
    """Read AI/policy validation findings strictly as separate advisory evidence."""
    val_record = (
        db.query(ValidationResult)
        .filter(
            ValidationResult.document_id == document.id,
            ValidationResult.organization_id == document.organization_id,
        )
        .first()
    )
    latest_run = (
        db.query(PolicyValidationRun)
        .filter(
            PolicyValidationRun.document_id == document.id,
            PolicyValidationRun.organization_id == document.organization_id,
        )
        .order_by(PolicyValidationRun.created_at.desc())
        .first()
    )
    if val_record is None and latest_run is None:
        return None
    return ValidationSummaryResponse(
        status=val_record.status if val_record else None,
        policy_version=val_record.policy_version if val_record else None,
        issues=list(val_record.issues or []) if val_record else [],
        latest_policy_run_status=latest_run.status if latest_run else None,
    )


def _build_workflow_response(db: Session, document: Document) -> DocumentWorkflowResponse:
    history_rows = (
        db.query(DocumentTransition)
        .filter(
            DocumentTransition.document_id == document.id,
            DocumentTransition.organization_id == document.organization_id,
        )
        .order_by(DocumentTransition.created_at.asc(), DocumentTransition.id.asc())
        .all()
    )
    latest_audit_row = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.document_id == document.id,
            AuditEvent.organization_id == document.organization_id,
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .first()
    )
    history = [DocumentTransitionResponse.model_validate(row) for row in history_rows]
    decision_value = (
        document.status.value
        if document.status in {DocumentStatus.APPROVED, DocumentStatus.REJECTED, DocumentStatus.CHANGES_REQUESTED}
        else None
    )
    return DocumentWorkflowResponse(
        document_id=document.id,
        organization_id=document.organization_id,
        status=document.status,
        assigned_reviewer_id=document.assigned_reviewer_id,
        assigned_approver_id=document.assigned_approver_id,
        revision_number=document.revision_number,
        workflow_updated_at=document.workflow_updated_at,
        last_decision_by=document.last_decision_by,
        last_decision_at=document.last_decision_at,
        last_decision_comment=document.last_decision_comment,
        decision=decision_value,
        comment=history[-1].comment if history else document.last_decision_comment,
        last_transition=history[-1] if history else None,
        audit_event=AuditEventResponse.model_validate(latest_audit_row) if latest_audit_row else None,
        history=history,
        validation_summary=_get_validation_summary(db, document),
    )


def _commit_transition(
    db: Session,
    *,
    document: Document,
    action: WorkflowAction,
    from_status: DocumentStatus,
    to_status: DocumentStatus,
    actor_id: str,
    actor_role: str,
    assigned_to_id: Optional[str] = None,
    previous_assignee_id: Optional[str] = None,
    comment: Optional[str] = None,
    storage: Optional[DocumentStorage] = None,
) -> DocumentWorkflowResponse:
    """Atomically persist document state updates, transition history, and audit event."""
    now = _utc_now()
    decision_name = _DECISION_ACTIONS.get(action)
    try:
        document.status = to_status
        document.workflow_updated_at = now
        if decision_name is not None:
            document.last_decision_by = actor_id
            document.last_decision_at = now
            document.last_decision_comment = comment

        transition = DocumentTransition(
            document_id=document.id,
            organization_id=document.organization_id,
            action=action.value,
            from_status=from_status.value,
            to_status=to_status.value,
            actor_id=actor_id,
            actor_role=actor_role,
            assigned_to_id=assigned_to_id,
            previous_assignee_id=previous_assignee_id,
            comment=comment,
            revision_number=document.revision_number,
            created_at=now,
        )
        audit_event = build_audit_event(
            document_id=document.id,
            organization_id=document.organization_id,
            event_type=_ACTION_TO_EVENT_TYPE.get(action, action.value),
            actor_id=actor_id,
            actor_type="USER",
            actor_role=actor_role,
            from_status=from_status.value,
            to_status=to_status.value,
            decision=decision_name,
            reason=comment,
            details={
                "action": action.value,
                "assigned_to_id": assigned_to_id,
                "previous_assignee_id": previous_assignee_id,
                "revision_number": document.revision_number,
            },
            created_at=now,
        )
        db.add(transition)
        db.add(audit_event)
        db.flush()
        db.commit()
        db.refresh(document)
        db.refresh(transition)
    except Exception:
        db.rollback()
        raise

    _sync_sidecar_metadata(document, storage=storage)

    # Dispatch in-app notifications (BE-13) - isolated and safe
    try:
        from services.notification import dispatch_workflow_notification
        dispatch_workflow_notification(
            db,
            document=document,
            transition=transition,
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            assigned_to_id=assigned_to_id,
            comment=comment,
        )
    except Exception as exc:
        logger.warning(
            "Notification dispatch failed for document %s: %s",
            document.id,
            exc,
        )

    return _build_workflow_response(db, document)


def get_document_workflow(
    db: Session,
    document_id: str,
    actor: dict,
) -> DocumentWorkflowResponse:
    """Fetch current workflow status, assignment state, history, and advisory validation."""
    org_id = str(actor.get("organization_id") or "").strip()
    if not actor.get("active", False) or not org_id:
        raise WorkflowError(403, "WORKFLOW_FORBIDDEN", "An active organization account is required.")
    document = _get_scoped_document(db, document_id, org_id)
    return _build_workflow_response(db, document)


def list_eligible_reviewers(
    db: Session,
    organization_id: str,
) -> List[EligibleReviewerResponse]:
    """Return active users eligible to review documents within the organization."""
    rows = (
        db.query(Membership, User)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.organization_id == str(organization_id),
            Membership.is_active.is_(True),
            User.is_active.is_(True),
            Membership.role.in_(ELIGIBLE_REVIEWER_ROLES),
        )
        .order_by(User.created_at.asc(), User.id.asc())
        .all()
    )
    return [
        EligibleReviewerResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=membership.role.value,
        )
        for membership, user in rows
    ]


def submit_document(
    db: Session,
    document_id: str,
    actor: dict,
    *,
    reviewer_id: Optional[str] = None,
    auto_route: bool = False,
    comment: Optional[str] = None,
    storage: Optional[DocumentStorage] = None,
) -> DocumentWorkflowResponse:
    """Submit a completed document for review, optionally assigning/routing a reviewer."""
    actor_id, actor_role = _require_role(actor, SUBMIT_CALLER_ROLES, "submit documents for review")
    document = _get_scoped_document(db, document_id, str(actor["organization_id"]))
    _validate_invalid_transition(document, COMPLETED_PRE_REVIEW_STATUSES, "submit")

    resolved_reviewer = _resolve_eligible_member(
        db,
        document.organization_id,
        reviewer_id,
        ELIGIBLE_REVIEWER_ROLES,
        MembershipRole.REVIEWER,
        auto_route=auto_route,
    )

    from_status = document.status
    to_status = DocumentStatus.IN_REVIEW if resolved_reviewer else DocumentStatus.SUBMITTED
    previous_reviewer = document.assigned_reviewer_id
    document.assigned_reviewer_id = resolved_reviewer
    document.revision_number = max(document.revision_number or 0, 0) + 1

    return _commit_transition(
        db,
        document=document,
        action=WorkflowAction.SUBMIT,
        from_status=from_status,
        to_status=to_status,
        actor_id=actor_id,
        actor_role=actor_role,
        assigned_to_id=resolved_reviewer,
        previous_assignee_id=previous_reviewer,
        comment=_normalize_comment(comment),
        storage=storage,
    )


def assign_reviewer(
    db: Session,
    document_id: str,
    actor: dict,
    *,
    reviewer_id: Optional[str] = None,
    auto_route: bool = False,
    comment: Optional[str] = None,
    storage: Optional[DocumentStorage] = None,
) -> DocumentWorkflowResponse:
    """Assign or reassign a submitted/in-review document to an eligible active reviewer."""
    actor_id, actor_role = _require_role(actor, ASSIGN_REVIEWER_CALLER_ROLES, "assign reviewers")
    document = _get_scoped_document(db, document_id, str(actor["organization_id"]))
    _validate_invalid_transition(document, ASSIGN_REVIEWER_ALLOWED_FROM, "assign reviewer to")

    if not (reviewer_id and reviewer_id.strip()) and not auto_route:
        raise WorkflowError(
            422,
            "REVIEWER_REQUIRED",
            "Provide an eligible reviewer_id or enable auto_route.",
        )

    resolved_reviewer = _resolve_eligible_member(
        db,
        document.organization_id,
        reviewer_id,
        ELIGIBLE_REVIEWER_ROLES,
        MembershipRole.REVIEWER,
        auto_route=auto_route,
    )
    previous_reviewer = document.assigned_reviewer_id
    action = (
        WorkflowAction.REASSIGN_REVIEWER
        if previous_reviewer is not None
        else WorkflowAction.ASSIGN_REVIEWER
    )
    from_status = document.status
    document.assigned_reviewer_id = resolved_reviewer
    document.revision_number = max(document.revision_number or 0, 1)

    return _commit_transition(
        db,
        document=document,
        action=action,
        from_status=from_status,
        to_status=DocumentStatus.IN_REVIEW,
        actor_id=actor_id,
        actor_role=actor_role,
        assigned_to_id=resolved_reviewer,
        previous_assignee_id=previous_reviewer,
        comment=_normalize_comment(comment),
        storage=storage,
    )


def request_changes(
    db: Session,
    document_id: str,
    actor: dict,
    *,
    comment: Optional[str] = None,
    storage: Optional[DocumentStorage] = None,
) -> DocumentWorkflowResponse:
    """Return a document to the submitter for changes; requires a non-empty comment."""
    actor_id, actor_role = _require_role(actor, REQUEST_CHANGES_REVIEWER_ROLES, "request changes")
    document = _get_scoped_document(db, document_id, str(actor["organization_id"]))
    _validate_invalid_transition(document, REQUEST_CHANGES_ALLOWED_FROM, "request changes on")

    if (
        document.status == DocumentStatus.PENDING_APPROVAL
        and actor_role not in REQUEST_CHANGES_APPROVAL_ROLES
    ):
        raise WorkflowError(
            403,
            "WORKFLOW_FORBIDDEN",
            f"Role '{actor_role}' is not authorized to request changes while pending approval.",
        )

    if document.status == DocumentStatus.IN_REVIEW:
        _enforce_assignee_ownership(
            actor_id,
            actor_role,
            document.assigned_reviewer_id,
            "REVIEWER",
            "reviewer",
        )
    elif document.status == DocumentStatus.PENDING_APPROVAL:
        _enforce_assignee_ownership(
            actor_id,
            actor_role,
            document.assigned_approver_id,
            "APPROVER",
            "approver",
        )

    cleaned_comment = _normalize_comment(comment)
    if not cleaned_comment:
        raise WorkflowError(
            422,
            "COMMENT_REQUIRED",
            "A non-empty comment explaining requested changes is required.",
        )

    from_status = document.status
    if from_status == DocumentStatus.PENDING_APPROVAL:
        document.assigned_approver_id = None
    document.last_decision_by = actor_id
    document.last_decision_comment = cleaned_comment

    return _commit_transition(
        db,
        document=document,
        action=WorkflowAction.REQUEST_CHANGES,
        from_status=from_status,
        to_status=DocumentStatus.CHANGES_REQUESTED,
        actor_id=actor_id,
        actor_role=actor_role,
        comment=cleaned_comment,
        storage=storage,
    )


def resubmit_document(
    db: Session,
    document_id: str,
    actor: dict,
    *,
    reviewer_id: Optional[str] = None,
    auto_route: bool = False,
    comment: Optional[str] = None,
    storage: Optional[DocumentStorage] = None,
) -> DocumentWorkflowResponse:
    """Resubmit a CHANGES_REQUESTED document while preserving full transition history."""
    actor_id, actor_role = _require_role(actor, SUBMIT_CALLER_ROLES, "resubmit documents")
    document = _get_scoped_document(db, document_id, str(actor["organization_id"]))
    _validate_invalid_transition(document, RESUBMIT_ALLOWED_FROM, "resubmit")

    previous_reviewer = document.assigned_reviewer_id
    resolved_reviewer: Optional[str] = None

    if reviewer_id is not None and reviewer_id.strip():
        resolved_reviewer = _resolve_eligible_member(
            db,
            document.organization_id,
            reviewer_id,
            ELIGIBLE_REVIEWER_ROLES,
            MembershipRole.REVIEWER,
        )
    elif previous_reviewer:
        # Preserve prior eligible reviewer if still active in the organization.
        try:
            resolved_reviewer = _resolve_eligible_member(
                db,
                document.organization_id,
                previous_reviewer,
                ELIGIBLE_REVIEWER_ROLES,
                MembershipRole.REVIEWER,
            )
        except WorkflowError:
            resolved_reviewer = _resolve_eligible_member(
                db,
                document.organization_id,
                None,
                ELIGIBLE_REVIEWER_ROLES,
                MembershipRole.REVIEWER,
                auto_route=auto_route,
            )
    elif auto_route:
        resolved_reviewer = _resolve_eligible_member(
            db,
            document.organization_id,
            None,
            ELIGIBLE_REVIEWER_ROLES,
            MembershipRole.REVIEWER,
            auto_route=True,
        )

    from_status = document.status
    to_status = DocumentStatus.IN_REVIEW if resolved_reviewer else DocumentStatus.SUBMITTED
    document.assigned_reviewer_id = resolved_reviewer
    document.revision_number = max(document.revision_number or 0, 1) + 1

    return _commit_transition(
        db,
        document=document,
        action=WorkflowAction.RESUBMIT,
        from_status=from_status,
        to_status=to_status,
        actor_id=actor_id,
        actor_role=actor_role,
        assigned_to_id=resolved_reviewer,
        previous_assignee_id=previous_reviewer,
        comment=_normalize_comment(comment),
        storage=storage,
    )


def submit_for_approval(
    db: Session,
    document_id: str,
    actor: dict,
    *,
    approver_id: Optional[str] = None,
    auto_route: bool = False,
    comment: Optional[str] = None,
    storage: Optional[DocumentStorage] = None,
) -> DocumentWorkflowResponse:
    """Advance an IN_REVIEW document to PENDING_APPROVAL and optionally route to an approver."""
    actor_id, actor_role = _require_role(
        actor,
        SUBMIT_FOR_APPROVAL_CALLER_ROLES,
        "forward documents for approval",
    )
    document = _get_scoped_document(db, document_id, str(actor["organization_id"]))
    _validate_invalid_transition(document, SUBMIT_FOR_APPROVAL_ALLOWED_FROM, "forward for approval")
    _enforce_assignee_ownership(
        actor_id,
        actor_role,
        document.assigned_reviewer_id,
        "REVIEWER",
        "reviewer",
    )

    resolved_approver = _resolve_eligible_member(
        db,
        document.organization_id,
        approver_id,
        ELIGIBLE_APPROVER_ROLES,
        MembershipRole.APPROVER,
        auto_route=auto_route,
        error_code="INELIGIBLE_APPROVER",
        no_candidate_code="NO_ELIGIBLE_APPROVER",
        role_label="approver",
    )
    from_status = document.status
    previous_approver = document.assigned_approver_id
    document.assigned_approver_id = resolved_approver

    return _commit_transition(
        db,
        document=document,
        action=WorkflowAction.SUBMIT_FOR_APPROVAL,
        from_status=from_status,
        to_status=DocumentStatus.PENDING_APPROVAL,
        actor_id=actor_id,
        actor_role=actor_role,
        assigned_to_id=resolved_approver,
        previous_assignee_id=previous_approver,
        comment=_normalize_comment(comment),
        storage=storage,
    )


def decide_document(
    db: Session,
    document_id: str,
    actor: dict,
    *,
    approve: bool,
    reason: Optional[str] = None,
    comment: Optional[str] = None,
    storage: Optional[DocumentStorage] = None,
) -> DocumentWorkflowResponse:
    """Record an explicit human APPROVE or REJECT decision from an authorized approver."""
    action_label = "approve documents" if approve else "reject documents"
    actor_id, actor_role = _require_role(actor, APPROVER_CALLER_ROLES, action_label)
    document = _get_scoped_document(db, document_id, str(actor["organization_id"]))
    _validate_invalid_transition(
        document,
        DECISION_ALLOWED_FROM,
        "approve" if approve else "reject",
    )
    _enforce_assignee_ownership(
        actor_id,
        actor_role,
        document.assigned_approver_id,
        "APPROVER",
        "approver",
    )

    resolved_reason = _normalize_comment(reason) or _normalize_comment(comment)
    from_status = document.status
    to_status = DocumentStatus.APPROVED if approve else DocumentStatus.REJECTED
    action = WorkflowAction.APPROVE if approve else WorkflowAction.REJECT

    return _commit_transition(
        db,
        document=document,
        action=action,
        from_status=from_status,
        to_status=to_status,
        actor_id=actor_id,
        actor_role=actor_role,
        comment=resolved_reason,
        storage=storage,
    )


def _to_queue_item(document: Document) -> QueueDocumentItemResponse:
    return QueueDocumentItemResponse(
        document_id=document.id,
        organization_id=document.organization_id,
        uploaded_by=document.uploaded_by,
        filename=document.filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        classification=document.classification,
        classification_confidence=document.classification_confidence,
        assigned_reviewer_id=document.assigned_reviewer_id,
        assigned_approver_id=document.assigned_approver_id,
        revision_number=document.revision_number,
        upload_timestamp=document.upload_timestamp,
        workflow_updated_at=document.workflow_updated_at,
        last_decision_by=document.last_decision_by,
        last_decision_at=document.last_decision_at,
        last_decision_comment=document.last_decision_comment,
    )


def _enforce_document_read_permission(
    document: Document,
    actor_id: str,
    actor_role: str,
) -> None:
    if actor_role in ADMIN_OVERRIDE_ROLES or actor_role in {"AUDITOR", "COMPLIANCE"}:
        return
    if actor_role == "SUBMITTER":
        if document.uploaded_by != actor_id:
            raise WorkflowError(
                403,
                "WORKFLOW_FORBIDDEN",
                "Submitters may only view their own documents.",
            )
        return
    if actor_role == "REVIEWER":
        if document.assigned_reviewer_id not in (None, actor_id):
            raise WorkflowError(
                403,
                "WORKFLOW_FORBIDDEN",
                "Document is assigned to another reviewer.",
            )
        return
    if actor_role == "APPROVER":
        if document.assigned_approver_id not in (None, actor_id):
            raise WorkflowError(
                403,
                "WORKFLOW_FORBIDDEN",
                "Document is assigned to another approver.",
            )
        return
    raise WorkflowError(403, "WORKFLOW_FORBIDDEN", "Not permitted to view this document.")


def _load_ocr_text(document_id: str, storage: Optional[DocumentStorage]) -> Optional[str]:
    try:
        doc_storage = storage or DocumentStorage()
        meta_path = doc_storage.base_dir / "metadata" / f"{document_id}.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            ocr = meta.get("ocr_text")
            if isinstance(ocr, str) and ocr.strip():
                return ocr
    except Exception:
        pass
    return None


def get_review_queue(
    db: Session,
    actor: dict,
    *,
    status_filter: Optional[str] = None,
    assigned_to_me: bool = False,
    classification: Optional[str] = None,
) -> ReviewQueueResponse:
    """Return documents in the caller's organization that the caller is permitted to review."""
    actor_id, actor_role = _require_role(actor, REVIEW_QUEUE_CALLER_ROLES, "view the review queue")
    org_id = str(actor["organization_id"])

    query = db.query(Document).filter(Document.organization_id == org_id)

    if actor_role in ADMIN_OVERRIDE_ROLES:
        allowed_statuses = REVIEWER_QUEUE_STATUSES
    elif actor_role == "APPROVER":
        allowed_statuses = APPROVER_QUEUE_STATUSES
        if assigned_to_me:
            query = query.filter(Document.assigned_approver_id == actor_id)
        else:
            query = query.filter(
                or_(
                    Document.assigned_approver_id.is_(None),
                    Document.assigned_approver_id == actor_id,
                )
            )
    else:
        allowed_statuses = REVIEWER_QUEUE_STATUSES
        if assigned_to_me:
            query = query.filter(Document.assigned_reviewer_id == actor_id)
        else:
            query = query.filter(
                or_(
                    Document.assigned_reviewer_id == actor_id,
                    (Document.status == DocumentStatus.SUBMITTED) & (Document.assigned_reviewer_id.is_(None)),
                )
            )

    if actor_role in ADMIN_OVERRIDE_ROLES and assigned_to_me:
        query = query.filter(
            or_(
                Document.assigned_reviewer_id == actor_id,
                Document.assigned_approver_id == actor_id,
            )
        )

    query = query.filter(Document.status.in_(allowed_statuses))

    if status_filter is not None and status_filter.strip():
        try:
            target_status = DocumentStatus(status_filter.strip().upper())
        except ValueError as exc:
            raise WorkflowError(
                422,
                "INVALID_QUEUE_FILTER",
                f"Unknown document status '{status_filter}'.",
            ) from exc
        query = query.filter(Document.status == target_status)

    if classification is not None and classification.strip():
        query = query.filter(Document.classification == classification.strip())

    docs = query.order_by(Document.workflow_updated_at.desc(), Document.upload_timestamp.desc()).all()
    items = [_to_queue_item(doc) for doc in docs]
    return ReviewQueueResponse(items=items, total=len(items))


def get_approval_queue(
    db: Session,
    actor: dict,
    *,
    assigned_to_me: bool = False,
) -> ReviewQueueResponse:
    """Return documents awaiting human approval that the caller is permitted to decide on."""
    actor_id, actor_role = _require_role(actor, APPROVAL_QUEUE_CALLER_ROLES, "view the approval queue")
    org_id = str(actor["organization_id"])

    query = db.query(Document).filter(
        Document.organization_id == org_id,
        Document.status.in_(APPROVER_QUEUE_STATUSES),
    )

    if actor_role == "APPROVER":
        if assigned_to_me:
            query = query.filter(Document.assigned_approver_id == actor_id)
        else:
            query = query.filter(
                or_(
                    Document.assigned_approver_id.is_(None),
                    Document.assigned_approver_id == actor_id,
                )
            )
    elif assigned_to_me:
        query = query.filter(Document.assigned_approver_id == actor_id)

    docs = query.order_by(Document.workflow_updated_at.desc(), Document.upload_timestamp.desc()).all()
    items = [_to_queue_item(doc) for doc in docs]
    return ReviewQueueResponse(items=items, total=len(items))


def get_document_review_detail(
    db: Session,
    document_id: str,
    actor: dict,
    *,
    storage: Optional[DocumentStorage] = None,
) -> DocumentReviewDetailResponse:
    """Return full permitted review context: document, extractions, validation evidence, comments, and audit."""
    actor_id, actor_role = _require_role(
        actor,
        {"SUBMITTER", "REVIEWER", "APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN", "AUDITOR", "COMPLIANCE"},
        "view document review details",
    )
    document = _get_scoped_document(db, document_id, str(actor["organization_id"]))
    _enforce_document_read_permission(document, actor_id, actor_role)

    extraction_rows = (
        db.query(Extraction)
        .filter(Extraction.document_id == document.id)
        .order_by(Extraction.field_name.asc())
        .all()
    )
    validation_row = (
        db.query(ValidationResult)
        .filter(
            ValidationResult.document_id == document.id,
            ValidationResult.organization_id == document.organization_id,
        )
        .first()
    )
    policy_runs = (
        db.query(PolicyValidationRun)
        .filter(
            PolicyValidationRun.document_id == document.id,
            PolicyValidationRun.organization_id == document.organization_id,
        )
        .order_by(PolicyValidationRun.created_at.desc(), PolicyValidationRun.id.desc())
        .all()
    )
    comment_rows = (
        db.query(ReviewComment)
        .filter(
            ReviewComment.document_id == document.id,
            ReviewComment.organization_id == document.organization_id,
        )
        .order_by(ReviewComment.created_at.asc(), ReviewComment.id.asc())
        .all()
    )
    transition_rows = (
        db.query(DocumentTransition)
        .filter(
            DocumentTransition.document_id == document.id,
            DocumentTransition.organization_id == document.organization_id,
        )
        .order_by(DocumentTransition.created_at.asc(), DocumentTransition.id.asc())
        .all()
    )
    audit_rows = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.document_id == document.id,
            AuditEvent.organization_id == document.organization_id,
        )
        .order_by(AuditEvent.created_at.asc(), AuditEvent.sequence_no.asc(), AuditEvent.id.asc())
        .all()
    )

    return DocumentReviewDetailResponse(
        document=_to_queue_item(document),
        extractions=[ReviewExtractionItemResponse.model_validate(row) for row in extraction_rows],
        ocr_text=_load_ocr_text(document.id, storage),
        validation=ReviewValidationEvidenceResponse.model_validate(validation_row) if validation_row else None,
        policy_validation_runs=[
            ReviewPolicyValidationRunResponse(
                id=run.id,
                status=run.status,
                summary=run.summary,
                retrieval_outcome=run.retrieval_outcome,
                policy_versions=list(run.policy_versions or []),
                requested_by=run.requested_by,
                created_at=run.created_at,
                findings=[
                    ReviewPolicyFindingResponse.model_validate(finding)
                    for finding in run.findings
                ],
            )
            for run in policy_runs
        ],
        comments=[ReviewCommentResponse.model_validate(row) for row in comment_rows],
        history=[DocumentTransitionResponse.model_validate(row) for row in transition_rows],
        audit_events=[AuditEventResponse.model_validate(row) for row in audit_rows],
    )


def add_review_comment(
    db: Session,
    document_id: str,
    actor: dict,
    *,
    comment: Optional[str] = None,
) -> ReviewCommentResponse:
    """Persist a standalone review comment together with an audit event atomically."""
    actor_id, actor_role = _require_role(actor, REVIEW_COMMENT_CALLER_ROLES, "submit review comments")
    document = _get_scoped_document(db, document_id, str(actor["organization_id"]))
    _validate_invalid_transition(document, REVIEW_COMMENT_ALLOWED_STATUSES, "comment on")
    _enforce_assignee_ownership(actor_id, actor_role, document.assigned_reviewer_id, "REVIEWER", "reviewer")
    _enforce_assignee_ownership(actor_id, actor_role, document.assigned_approver_id, "APPROVER", "approver")

    cleaned_comment = _normalize_comment(comment)
    if not cleaned_comment:
        raise WorkflowError(
            422,
            "COMMENT_REQUIRED",
            "A non-empty review comment is required.",
        )

    now = _utc_now()
    revision = max(document.revision_number or 1, 1)
    try:
        review_comment = ReviewComment(
            document_id=document.id,
            organization_id=document.organization_id,
            author_id=actor_id,
            author_role=actor_role,
            comment=cleaned_comment,
            revision_number=revision,
            created_at=now,
        )
        audit_event = build_audit_event(
            document_id=document.id,
            organization_id=document.organization_id,
            event_type="REVIEW_COMMENT_ADDED",
            actor_id=actor_id,
            actor_type="USER",
            actor_role=actor_role,
            from_status=document.status.value,
            to_status=document.status.value,
            decision=None,
            reason=cleaned_comment,
            details={"revision_number": revision},
            created_at=now,
        )
        db.add(review_comment)
        db.add(audit_event)
        db.flush()
        db.commit()
        db.refresh(review_comment)
    except Exception:
        db.rollback()
        raise

    return ReviewCommentResponse.model_validate(review_comment)


def get_document_audit_trail(
    db: Session,
    document_id: str,
    actor: dict,
) -> DocumentAuditTrailResponse:
    """Retrieve chronological audit events for a permitted document."""
    actor_id, actor_role = _require_role(
        actor,
        {"SUBMITTER", "REVIEWER", "APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN", "AUDITOR", "COMPLIANCE"},
        "view document audit trail",
    )
    document = _get_scoped_document(db, document_id, str(actor["organization_id"]))
    _enforce_document_read_permission(document, actor_id, actor_role)

    events = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.document_id == document.id,
            AuditEvent.organization_id == document.organization_id,
        )
        .order_by(AuditEvent.created_at.asc(), AuditEvent.sequence_no.asc(), AuditEvent.id.asc())
        .all()
    )
    return DocumentAuditTrailResponse(
        document_id=document.id,
        organization_id=document.organization_id,
        status=document.status,
        events=[AuditEventResponse.model_validate(event) for event in events],
    )
