"""
BE-09 / DB-05: ValidationResult persistence model.
Stores document compliance validation outcomes, policy versions, issues, and citations.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String

try:
    from app.db.base import Base
except ImportError:
    from backend.app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ValidationResult(Base):
    """Compliance validation verdict for a processed document against active policy."""
    __tablename__ = "validation_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_id = Column(String(36), ForeignKey("policies.id", ondelete="SET NULL"), nullable=True, index=True)
    policy_version = Column(String, nullable=True)  # Snapshot version used for NFR-AUD-03 auditability
    status = Column(String, nullable=False, default="PASS")  # PASS, FAIL, REVIEW_REQUIRED
    issues = Column(JSON, nullable=False, default=list)  # [{"rule": str, "severity": str, "message": str}]
    evidence = Column(JSON, nullable=False, default=list)  # [{"source": str, "reference": str}]
    validated_by = Column(String(36), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    def __repr__(self) -> str:
        return f"<ValidationResult doc={self.document_id} status={self.status} policy={self.policy_id}@{self.policy_version}>"
