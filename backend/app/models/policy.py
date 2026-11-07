"""
BE-08 / DB-04: Policy and PolicyVersion persistence models.
Represents organization-scoped policies with immutable version history.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

try:
    from app.db.base import Base
except ImportError:
    from backend.app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Policy(Base):
    """Organization compliance or validation policy."""
    __tablename__ = "policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    domain = Column(String, nullable=False, index=True)  # e.g. financial, hr, academic, compliance
    current_version = Column(String, nullable=False, default="v1")
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    versions = relationship(
        "PolicyVersion",
        back_populates="policy",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PolicyVersion.created_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<Policy id={self.id} org={self.organization_id} domain={self.domain} v={self.current_version}>"


class PolicyVersion(Base):
    """Historical immutable snapshot of a policy version (NFR-AUD-03)."""
    __tablename__ = "policy_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    policy_id = Column(String(36), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    changelog = Column(String, nullable=True)
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    policy = relationship("Policy", back_populates="versions")

    def __repr__(self) -> str:
        return f"<PolicyVersion id={self.id} policy={self.policy_id} version={self.version}>"
