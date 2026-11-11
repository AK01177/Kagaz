"""Persisted, evidence-grounded policy validation runs."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PolicyValidationRun(Base):
    __tablename__ = "policy_validation_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), nullable=False, index=True)
    requested_by = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False)
    summary = Column(Text, nullable=False)
    retrieval_outcome = Column(String(32), nullable=False)
    policy_versions = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    findings = relationship("PolicyValidationFinding", back_populates="run", cascade="all, delete-orphan")


class PolicyValidationFinding(Base):
    __tablename__ = "policy_validation_findings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("policy_validation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), nullable=False)
    requirement = Column(Text, nullable=False)
    explanation = Column(Text, nullable=False)
    field_name = Column(String(255), nullable=True)
    document_value = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    source_references = Column(JSON, nullable=False, default=list)

    run = relationship("PolicyValidationRun", back_populates="findings")
