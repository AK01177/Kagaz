"""
API routes for in-app workflow notifications (BE-13).

Provides endpoints for authenticated users to list their own notifications,
view unread counts, and mark individual or all notifications as read.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.auth import require_workflow_actor
from app.db.session import get_db
from app.schemas.notification import (
    MarkReadResponse,
    NotificationListResponse,
    NotificationResponse,
)
from services.notification import (
    list_notifications,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _require_db(db: Optional[Session]) -> Session:
    if db is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "DATABASE_UNAVAILABLE",
                "message": "Database connection is required for notifications.",
            },
        )
    return db


@router.get("", response_model=NotificationListResponse)
def get_user_notifications(
    actor: Annotated[dict, Depends(require_workflow_actor)],
    unread_only: bool = Query(default=False, description="Filter for unread notifications only"),
    limit: int = Query(default=50, ge=1, le=100, description="Page limit"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> NotificationListResponse:
    """List in-app notifications for the authenticated user in their organization."""
    session = _require_db(db)
    user_id = str(actor.get("sub") or "").strip()
    org_id = str(actor.get("organization_id") or "").strip()

    items, total, unread_count = list_notifications(
        session,
        recipient_user_id=user_id,
        organization_id=org_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )

    return NotificationListResponse(
        items=[NotificationResponse.model_validate(item) for item in items],
        total=total,
        unread_count=unread_count,
    )


@router.patch("/{notification_id}/read", response_model=MarkReadResponse)
@router.post("/{notification_id}/read", response_model=MarkReadResponse)
def mark_read_endpoint(
    notification_id: str,
    actor: Annotated[dict, Depends(require_workflow_actor)],
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> MarkReadResponse:
    """Mark a specific notification as read."""
    session = _require_db(db)
    user_id = str(actor.get("sub") or "").strip()
    org_id = str(actor.get("organization_id") or "").strip()

    notif = mark_notification_as_read(
        session,
        notification_id=notification_id,
        recipient_user_id=user_id,
        organization_id=org_id,
    )
    if notif is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "NOTIFICATION_NOT_FOUND",
                "message": "Notification not found or access denied.",
            },
        )

    return MarkReadResponse(
        success=True,
        notification_id=notif.id,
        updated_count=1,
    )


@router.post("/read-all", response_model=MarkReadResponse)
def mark_all_read_endpoint(
    actor: Annotated[dict, Depends(require_workflow_actor)],
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> MarkReadResponse:
    """Mark all unread notifications for the caller as read."""
    session = _require_db(db)
    user_id = str(actor.get("sub") or "").strip()
    org_id = str(actor.get("organization_id") or "").strip()

    count = mark_all_notifications_as_read(
        session,
        recipient_user_id=user_id,
        organization_id=org_id,
    )

    return MarkReadResponse(
        success=True,
        updated_count=count,
    )
