"""
BE-10: Document Workflow State Machine — persistence models.

WorkflowTransition records every state change as an immutable audit trail.
The Document.status column always reflects the current state; this table
provides the full history of how it got there.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class WorkflowAction(str, enum.Enum):
    """
    Permitted workflow actions that drive DocumentStatus transitions.

    SUBMIT           Submitter declares the document ready for review.
    ASSIGN           ORG_ADMIN or REVIEWER routes the document to a specific reviewer.
    REQUEST_CHANGES  Reviewer sends the document back; a comment is mandatory.
    RESUBMIT         Submitter addresses feedback and resubmits.
    APPROVE          Approver or ORG_ADMIN accepts the document.
    REJECT           Approver or ORG_ADMIN rejects the document.
    """
    SUBMIT = "SUBMIT"
    ASSIGN = "ASSIGN"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    RESUBMIT = "RESUBMIT"
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class WorkflowTransition(Base):
    """
    Immutable record of a single workflow state change.

    Every transition captures the full before/after state, the actor who
    triggered it, and an optional comment (required for REQUEST_CHANGES).
    Records are never updated or deleted — history is append-only.
    """
    __tablename__ = "workflow_transitions"

    __table_args__ = (
        Index("ix_workflow_transitions_document_id", "document_id"),
        Index("ix_workflow_transitions_organization_id", "organization_id"),
        Index("ix_workflow_transitions_actor_id", "actor_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(String(36), nullable=False, index=True)

    # The user who triggered this transition.
    actor_id = Column(String(36), nullable=False)
    actor_role = Column(String(50), nullable=False)

    action = Column(Enum(WorkflowAction), nullable=False)

    # Snapshot the state before and after for full history without join queries.
    from_status = Column(String(50), nullable=False)
    to_status = Column(String(50), nullable=False)

    # Required for REQUEST_CHANGES; optional for other actions.
    comment = Column(Text, nullable=True)

    # For ASSIGN: the user being assigned as reviewer.
    assigned_to = Column(String(36), nullable=True)

    transitioned_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    document = relationship("Document")

    def __repr__(self) -> str:
        return (
            f"<WorkflowTransition id={self.id} "
            f"doc={self.document_id} "
            f"{self.from_status}->{self.to_status} "
            f"by={self.actor_id}>"
        )
