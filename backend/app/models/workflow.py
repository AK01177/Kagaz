"""
Workflow audit trail persistence models for document lifecycle transitions.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    event,
)
from sqlalchemy.orm import Session, relationship

from app.db.base import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class WorkflowAction(str, enum.Enum):
    """Explicit human/system workflow transition actions."""

    SUBMIT = "SUBMIT"
    ASSIGN_REVIEWER = "ASSIGN_REVIEWER"
    REASSIGN_REVIEWER = "REASSIGN_REVIEWER"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    RESUBMIT = "RESUBMIT"
    SUBMIT_FOR_APPROVAL = "SUBMIT_FOR_APPROVAL"
    ASSIGN_APPROVER = "ASSIGN_APPROVER"
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class DocumentTransition(Base):
    """
    Append-only audit record capturing every workflow transition and assignment.

    Persisted in the same database transaction as the Document state update so
    state and history never diverge across retries or resubmissions.
    """

    __tablename__ = "document_transitions"

    __table_args__ = (
        Index("ix_document_transitions_doc_created", "document_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(String(36), nullable=False, index=True)
    action = Column(String(64), nullable=False)
    from_status = Column(String(64), nullable=False)
    to_status = Column(String(64), nullable=False)
    actor_id = Column(String(36), nullable=False, index=True)
    actor_role = Column(String(64), nullable=False)
    assigned_to_id = Column(String(36), nullable=True, index=True)
    previous_assignee_id = Column(String(36), nullable=True)
    comment = Column(Text, nullable=True)
    revision_number = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    document = relationship("Document", back_populates="transitions")

    def __repr__(self) -> str:
        return (
            f"<DocumentTransition doc={self.document_id} action={self.action} "
            f"{self.from_status}->{self.to_status}>"
        )


class ReviewComment(Base):
    """Persistent human review note attached to a document."""

    __tablename__ = "review_comments"

    __table_args__ = (
        Index("ix_review_comments_doc_created", "document_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(String(36), nullable=False, index=True)
    author_id = Column(String(36), nullable=False, index=True)
    author_role = Column(String(64), nullable=False)
    comment = Column(Text, nullable=False)
    revision_number = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    document = relationship("Document", back_populates="review_comments")

    def __repr__(self) -> str:
        return f"<ReviewComment doc={self.document_id} author={self.author_id}>"


class AuditEvent(Base):
    """First-class audit trail event created atomically on comments, transitions, and decisions."""

    __tablename__ = "audit_events"

    __table_args__ = (
        Index("ix_audit_events_doc_created", "document_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    actor_id = Column(String(64), nullable=False, index=True)
    actor_type = Column(String(16), nullable=False, default="USER")
    actor_role = Column(String(64), nullable=False)
    from_status = Column(String(64), nullable=True)
    to_status = Column(String(64), nullable=True)
    decision = Column(String(32), nullable=True)
    reason = Column(Text, nullable=True)
    details = Column(JSON, nullable=False, default=dict)
    sequence_no = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    document = relationship("Document", back_populates="audit_events")

    def __repr__(self) -> str:
        return f"<AuditEvent doc={self.document_id} type={self.event_type} actor={self.actor_id}>"


class AuditImmutabilityError(ValueError):
    """Raised when attempting to update or delete append-only audit records."""


_IMMUTABLE_AUDIT_MODELS = (AuditEvent, DocumentTransition)


@event.listens_for(Session, "before_flush")
def _enforce_audit_immutability(session: Session, _flush_context, _instances) -> None:
    """Prevent normal application code from altering or deleting persisted audit history."""
    for obj in session.dirty:
        if isinstance(obj, _IMMUTABLE_AUDIT_MODELS) and session.is_modified(obj, include_collections=False):
            raise AuditImmutabilityError(f"{type(obj).__name__} records are immutable and cannot be modified.")

    deleted_document_ids = {
        obj.id for obj in session.deleted if getattr(obj, "__tablename__", None) == "documents"
    }
    for obj in session.deleted:
        if isinstance(obj, _IMMUTABLE_AUDIT_MODELS) and obj.document_id not in deleted_document_ids:
            raise AuditImmutabilityError(f"{type(obj).__name__} records are immutable and cannot be deleted.")
