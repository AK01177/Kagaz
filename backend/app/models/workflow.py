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
    String,
    Text,
)
from sqlalchemy.orm import relationship

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
