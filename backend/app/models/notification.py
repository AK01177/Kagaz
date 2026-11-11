"""
BE-13: Notification persistence model.

One row per in-app notification. Notifications are created by workflow
events (assignment, request-changes, approval, rejection) and are
read-only after creation except for the `is_read` flag.

Design decisions
----------------
* idempotency_key — callers supply a stable key (e.g. transition_id +
  event_type) so retry/duplicate workflow events never create duplicate
  notifications. The unique constraint on this column enforces it at the
  database level.
* Notification failure must NOT break the main workflow — the service
  wraps DB writes in try/except and logs on failure.
* No document content, extracted field values, or secrets are stored.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)

from app.db.base import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Notification(Base):
    """
    In-app notification for a workflow event requiring a user's attention.

    Columns
    -------
    id                  UUID primary key.
    recipient_user_id   The user who should see this notification.
    organization_id     Org-scoping — users only see their own org's events.
    document_id         Optional FK to the related document (NULL for org-level events).
    notification_type   Short machine-readable type: ASSIGNED, CHANGES_REQUESTED,
                        APPROVED, REJECTED, RESUBMITTED.
    title               Short human-readable headline (max 255 chars).
    body                Optional longer description.
    is_read             False on creation; set True by the mark-read endpoint.
    idempotency_key     Stable caller-supplied key to prevent duplicate rows on retry.
    created_at          UTC timestamp set on insert.
    """

    __tablename__ = "notifications"

    __table_args__ = (
        # One notification per (recipient, event) — prevents duplicates on retry.
        UniqueConstraint("idempotency_key", name="uq_notifications_idempotency_key"),
        Index("ix_notifications_recipient_read", "recipient_user_id", "is_read"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    recipient_user_id = Column(String(36), nullable=False, index=True)
    organization_id = Column(String(36), nullable=False, index=True)

    document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Machine-readable event type for frontend filtering.
    notification_type = Column(String(64), nullable=False)

    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)

    is_read = Column(Boolean, nullable=False, default=False, index=True)

    # Stable key: e.g. "transition:{transition_id}:ASSIGNED"
    # Unique constraint ensures retries are idempotent.
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    def __repr__(self) -> str:
        return (
            f"<Notification id={self.id} "
            f"type={self.notification_type} "
            f"recipient={self.recipient_user_id} "
            f"read={self.is_read}>"
        )
