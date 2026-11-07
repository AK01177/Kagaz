"""
DB-02: Organization Membership and Role persistence models.
Represents the many-to-many link between Users and Organizations with assigned RBAC roles.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

try:
    from app.db.base import Base
except ImportError:
    from backend.app.db.base import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class MembershipRole(str, enum.Enum):
    """
    Standard RBAC roles defined in Kagaz architecture and API design.
    """
    SUBMITTER = "SUBMITTER"
    REVIEWER = "REVIEWER"
    APPROVER = "APPROVER"
    ORG_ADMIN = "ORG_ADMIN"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    COMPLIANCE = "COMPLIANCE"
    AUDITOR = "AUDITOR"


class Membership(Base):
    """
    Organization membership entity.
    Links a User to an Organization and establishes their verified role.
    """
    __tablename__ = "memberships"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_memberships_org_user",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(
        Enum(MembershipRole, name="membershiprole"),
        nullable=False,
        default=MembershipRole.SUBMITTER,
        index=True,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    organization = relationship("Organization", back_populates="memberships")
    user = relationship("User", back_populates="memberships")

    def __repr__(self) -> str:
        return f"<Membership org_id={self.organization_id} user_id={self.user_id} role={self.role}>"

