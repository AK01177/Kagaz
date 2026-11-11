"""
BE-13: In-app notification service.

Provides:
- notify() / dispatch_workflow_notification(): Called by workflow events to create notifications.
- list_notifications(): Queries notifications filtered strictly by recipient_user_id and organization_id.
- mark_notification_as_read(): Marks a single notification as read.
- mark_all_notifications_as_read(): Marks all unread notifications as read.

Rules & Guarantees:
- Tenant & Recipient Isolation: Users see ONLY their own notifications in their organization.
- Idempotent: Retries do not create duplicate notifications (enforced by idempotency_key).
- Fault tolerant: Notification failure NEVER breaks the main workflow.
- Privacy & Compliance: No secret keys, extraction text, or passwords in notification messages.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.notification import Notification
from app.models.workflow import DocumentTransition, WorkflowAction

logger = logging.getLogger(__name__)


def _create_notification(
    db: Session,
    *,
    recipient_user_id: str,
    organization_id: str,
    notification_type: str,
    title: str,
    body: Optional[str] = None,
    document_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    commit: bool = True,
) -> Optional[Notification]:
    """Insert a single notification row with idempotent deduplication and safety."""
    if not recipient_user_id or not organization_id:
        return None

    try:
        if idempotency_key:
            existing = (
                db.query(Notification)
                .filter(Notification.idempotency_key == idempotency_key)
                .first()
            )
            if existing is not None:
                logger.debug(
                    "Notification skipped: idempotency_key=%s already exists",
                    idempotency_key,
                )
                return existing

        notif = Notification(
            recipient_user_id=recipient_user_id,
            organization_id=organization_id,
            document_id=document_id,
            notification_type=notification_type,
            title=title[:255],
            body=body[:2000] if body else None,
            idempotency_key=idempotency_key,
            is_read=False,
        )
        db.add(notif)
        if commit:
            db.commit()
            db.refresh(notif)
        else:
            db.flush()
        return notif
    except IntegrityError:
        db.rollback()
        logger.debug(
            "IntegrityError inserting notification (idempotency_key=%s); returning existing",
            idempotency_key,
        )
        if idempotency_key:
            return (
                db.query(Notification)
                .filter(Notification.idempotency_key == idempotency_key)
                .first()
            )
        return None
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(
            "Non-fatal notification creation failure for recipient %s: %s",
            recipient_user_id,
            exc,
        )
        return None


def notify(
    db: Optional[Session],
    *,
    recipient_user_id: str,
    organization_id: str,
    notification_type: str,
    title: str,
    body: Optional[str] = None,
    document_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Optional[Notification]:
    """Public helper to create an in-app notification safely."""
    if db is None:
        return None
    return _create_notification(
        db,
        recipient_user_id=recipient_user_id,
        organization_id=organization_id,
        notification_type=notification_type,
        title=title,
        body=body,
        document_id=document_id,
        idempotency_key=idempotency_key,
        commit=True,
    )


def dispatch_workflow_notification(
    db: Session,
    *,
    document: Document,
    transition: DocumentTransition,
    action: WorkflowAction,
    actor_id: str,
    actor_role: str,
    assigned_to_id: Optional[str] = None,
    comment: Optional[str] = None,
) -> None:
    """
    Dispatch workflow-triggered notifications for assignment, request-changes, and decisions.
    
    Wrapped in try/except so any notification error NEVER breaks the main workflow transaction.
    """
    try:
        doc_filename = document.filename or "Document"
        transition_id = transition.id

        if action in {WorkflowAction.ASSIGN_REVIEWER, WorkflowAction.REASSIGN_REVIEWER}:
            target_reviewer = assigned_to_id or document.assigned_reviewer_id
            if target_reviewer and target_reviewer != actor_id:
                notify(
                    db,
                    recipient_user_id=target_reviewer,
                    organization_id=document.organization_id,
                    notification_type="ASSIGNED",
                    title=f"Document assigned: {doc_filename}",
                    body=f"You have been assigned to review document '{doc_filename}'.",
                    document_id=document.id,
                    idempotency_key=f"transition:{transition_id}:{target_reviewer}:ASSIGNED",
                )

        elif action == WorkflowAction.SUBMIT:
            target_reviewer = assigned_to_id or document.assigned_reviewer_id
            if target_reviewer and target_reviewer != actor_id:
                notify(
                    db,
                    recipient_user_id=target_reviewer,
                    organization_id=document.organization_id,
                    notification_type="ASSIGNED",
                    title=f"New document submitted for review: {doc_filename}",
                    body=f"Document '{doc_filename}' has been submitted and assigned to you.",
                    document_id=document.id,
                    idempotency_key=f"transition:{transition_id}:{target_reviewer}:ASSIGNED",
                )

        elif action == WorkflowAction.REQUEST_CHANGES:
            target_submitter = document.uploaded_by
            if target_submitter and target_submitter != actor_id:
                body_text = f"Reviewer requested changes on '{doc_filename}'."
                if comment:
                    body_text += f" Reason: {comment}"
                notify(
                    db,
                    recipient_user_id=target_submitter,
                    organization_id=document.organization_id,
                    notification_type="CHANGES_REQUESTED",
                    title=f"Changes requested: {doc_filename}",
                    body=body_text,
                    document_id=document.id,
                    idempotency_key=f"transition:{transition_id}:{target_submitter}:CHANGES_REQUESTED",
                )

        elif action == WorkflowAction.RESUBMIT:
            target_reviewer = document.assigned_reviewer_id
            if target_reviewer and target_reviewer != actor_id:
                body_text = f"Document '{doc_filename}' was resubmitted after changes."
                if comment:
                    body_text += f" Note: {comment}"
                notify(
                    db,
                    recipient_user_id=target_reviewer,
                    organization_id=document.organization_id,
                    notification_type="RESUBMITTED",
                    title=f"Document resubmitted: {doc_filename}",
                    body=body_text,
                    document_id=document.id,
                    idempotency_key=f"transition:{transition_id}:{target_reviewer}:RESUBMITTED",
                )

        elif action == WorkflowAction.SUBMIT_FOR_APPROVAL:
            target_approver = assigned_to_id or document.assigned_approver_id
            if target_approver and target_approver != actor_id:
                notify(
                    db,
                    recipient_user_id=target_approver,
                    organization_id=document.organization_id,
                    notification_type="APPROVAL_REQUESTED",
                    title=f"Approval requested: {doc_filename}",
                    body=f"Document '{doc_filename}' has been reviewed and requires your approval.",
                    document_id=document.id,
                    idempotency_key=f"transition:{transition_id}:{target_approver}:APPROVAL_REQUESTED",
                )

        elif action == WorkflowAction.APPROVE:
            target_submitter = document.uploaded_by
            if target_submitter and target_submitter != actor_id:
                body_text = f"Your document '{doc_filename}' has been approved."
                if comment:
                    body_text += f" Note: {comment}"
                notify(
                    db,
                    recipient_user_id=target_submitter,
                    organization_id=document.organization_id,
                    notification_type="APPROVED",
                    title=f"Document approved: {doc_filename}",
                    body=body_text,
                    document_id=document.id,
                    idempotency_key=f"transition:{transition_id}:{target_submitter}:APPROVED",
                )

        elif action == WorkflowAction.REJECT:
            target_submitter = document.uploaded_by
            if target_submitter and target_submitter != actor_id:
                body_text = f"Your document '{doc_filename}' has been rejected."
                if comment:
                    body_text += f" Reason: {comment}"
                notify(
                    db,
                    recipient_user_id=target_submitter,
                    organization_id=document.organization_id,
                    notification_type="REJECTED",
                    title=f"Document rejected: {doc_filename}",
                    body=body_text,
                    document_id=document.id,
                    idempotency_key=f"transition:{transition_id}:{target_submitter}:REJECTED",
                )

    except Exception as exc:
        logger.warning(
            "Non-fatal error in dispatch_workflow_notification for doc %s action %s: %s",
            document.id,
            action,
            exc,
        )


def list_notifications(
    db: Session,
    *,
    recipient_user_id: str,
    organization_id: str,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[list[Notification], int, int]:
    """
    List notifications scoped strictly to the recipient user and organization.
    Returns (items, total_matching, unread_count).
    """
    base_query = db.query(Notification).filter(
        Notification.recipient_user_id == str(recipient_user_id),
        Notification.organization_id == str(organization_id),
    )

    unread_count = (
        db.query(func.count(Notification.id))
        .filter(
            Notification.recipient_user_id == str(recipient_user_id),
            Notification.organization_id == str(organization_id),
            Notification.is_read.is_(False),
        )
        .scalar()
        or 0
    )

    if unread_only:
        filtered_query = base_query.filter(Notification.is_read.is_(False))
    else:
        filtered_query = base_query

    total = filtered_query.count()
    items = (
        filtered_query.order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(min(limit, 100))
        .all()
    )

    return items, total, unread_count


def mark_notification_as_read(
    db: Session,
    *,
    notification_id: str,
    recipient_user_id: str,
    organization_id: str,
) -> Optional[Notification]:
    """Mark a notification read if owned by the caller in their organization."""
    notif = (
        db.query(Notification)
        .filter(
            Notification.id == str(notification_id),
            Notification.recipient_user_id == str(recipient_user_id),
            Notification.organization_id == str(organization_id),
        )
        .first()
    )
    if notif is None:
        return None

    if not notif.is_read:
        notif.is_read = True
        db.commit()
        db.refresh(notif)
    return notif


def mark_all_notifications_as_read(
    db: Session,
    *,
    recipient_user_id: str,
    organization_id: str,
) -> int:
    """Mark all unread notifications read for the given user in their organization."""
    count = (
        db.query(Notification)
        .filter(
            Notification.recipient_user_id == str(recipient_user_id),
            Notification.organization_id == str(organization_id),
            Notification.is_read.is_(False),
        )
        .update({Notification.is_read: True}, synchronize_session=False)
    )
    db.commit()
    return count
