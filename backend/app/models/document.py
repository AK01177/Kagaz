"""
BE-03: Storage and Metadata
Defines the persistence model for uploaded document metadata.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, DateTime, Enum

from app.db.base import Base


class DocumentStatus(str, enum.Enum):
    """Lifecycle status of a document as it moves through the ingestion pipeline."""
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    CLASSIFIED = "CLASSIFIED"
    FAILED = "FAILED"


class Document(Base):
    """
    Metadata record for a single uploaded document.

    Intentionally separate from extracted-field or validation-result
    tables (owned by BE-04 Classification and the Policy Validation
    issues) — this table only tracks identity, storage location, and
    lifecycle status.
    """
    __tablename__ = "documents"

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

    # Lifecycle
    status = Column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.UPLOADED, index=True)
    upload_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Populated once classification runs (BE-04) — nullable until then
    classification = Column(String, nullable=True)            # e.g. "invoice", "transcript"
    classification_confidence = Column(Float, nullable=True)  # 0.0–1.0

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename={self.filename} status={self.status}>"
