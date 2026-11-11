"""
BE-03: Storage and Metadata
Defines the persistence model for uploaded document metadata.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class DocumentStatus(str, enum.Enum):
    """Lifecycle status of a document through ingestion and human workflow."""

    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    CLASSIFIED = "CLASSIFIED"
    EXTRACTED = "EXTRACTED"
    VALIDATED = "VALIDATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"
    SUBMITTED = "SUBMITTED"
    IN_REVIEW = "IN_REVIEW"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Document(Base):
    """
    Metadata record for a single uploaded document.

    Intentionally separate from extracted-field or validation-result
    tables (owned by BE-04 Classification and the Policy Validation
    issues) — this table only tracks identity, storage location, and
    lifecycle status.
    """
    __tablename__ = "documents"

    __table_args__ = (
        CheckConstraint(
            "classification_confidence IS NULL OR (classification_confidence >= 0.0 AND classification_confidence <= 1.0)",
            name="ck_documents_classification_confidence_range",
        ),
    )

    # Stored as String(36) rather than a Postgres-native UUID column so
    # the model runs identically against Postgres (prod) and SQLite
    # (fast local tests) without a dialect-specific type. Can move to a
    # native UUID column later via Alembic if that portability stops
    # being useful.
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Multi-tenant scoping — required per architecture.md: every table
    # is scoped by organization_id so one org's documents are never
    # visible to, or processed against, another org's policies.
    organization_id = Column(String(36), nullable=False, index=True)
    uploaded_by = Column(String(36), nullable=False)

    # File identity
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)   # e.g. "application/pdf", "image/png"
    file_size = Column(Integer, nullable=False)   # bytes

    # Storage location (S3 key/path — not the file itself)
    storage_path = Column(String, nullable=False)

    # Lifecycle & assignment
    status = Column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.UPLOADED, index=True)
    upload_timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    assigned_reviewer_id = Column(String(36), nullable=True, index=True)
    assigned_approver_id = Column(String(36), nullable=True, index=True)
    revision_number = Column(Integer, nullable=False, default=0)
    workflow_updated_at = Column(DateTime(timezone=True), nullable=True)
    last_decision_by = Column(String(36), nullable=True)
    last_decision_comment = Column(Text, nullable=True)

    # Populated once classification runs (BE-04) — nullable until then
    classification = Column(String, nullable=True)            # e.g. "invoice", "transcript"
    classification_confidence = Column(Float, nullable=True)  # 0.0–1.0

    # Relationships
    extractions = relationship(
        "Extraction",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    transitions = relationship(
        "DocumentTransition",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentTransition.created_at",
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename={self.filename} status={self.status}>"
