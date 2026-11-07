import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class ExtractionStatus(str, enum.Enum):
    """Execution status for an extraction run."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ExtractionRun(Base):
    """Discrete execution record for a document field extraction attempt.

    Maintains the Document -> Extraction Run -> Extracted Fields hierarchy,
    providing complete audit history across re-extraction attempts without
    corrupting previous successful results.
    """

    __tablename__ = "extraction_runs"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = Column(
        Enum(ExtractionStatus, name="extractionstatus"),
        nullable=False,
        default=ExtractionStatus.SUCCESS,
        index=True,
    )

    document_type = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    document = relationship("Document", back_populates="extraction_runs")
    extractions = relationship(
        "Extraction",
        back_populates="extraction_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<ExtractionRun id={self.id} doc={self.document_id} status={self.status}>"


class Extraction(Base):
    """One structured extracted field belonging to a document and extraction run."""

    __tablename__ = "extractions"

    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_extractions_confidence_range",
        ),
        UniqueConstraint(
            "document_id",
            "field_name",
            name="uq_extractions_document_field",
        ),
    )

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    extraction_run_id = Column(
        String(36),
        ForeignKey("extraction_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    field_name = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    document = relationship("Document", back_populates="extractions")
    extraction_run = relationship("ExtractionRun", back_populates="extractions")
