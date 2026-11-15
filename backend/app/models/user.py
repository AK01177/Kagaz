"""
DB-02: User and UserProviderMapping persistence models.
Represents persistent identities and external provider-subject mappings.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
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


class User(Base):
    """
    User entity representing a registered individual identity across organizations.
    """
    __tablename__ = "users"

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_subject",
            name="uq_users_provider_subject",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    # Direct provider-subject attributes for single-provider accounts
    provider = Column(String, nullable=True)
    provider_subject = Column(String, nullable=True, index=True)

    # Relationships
    memberships = relationship(
        "Membership",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    provider_mappings = relationship(
        "UserProviderMapping",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


class UserProviderMapping(Base):
    """
    Explicit external provider-subject mapping table.
    Maps an external identity provider subject (e.g. Google sub, Azure OID, Auth0 ID)
    to a Kagaz user identity.
    """
    __tablename__ = "user_provider_mappings"

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_subject",
            name="uq_user_provider_mappings_provider_subject",
        ),
        Index(
            "ix_user_provider_mappings_lookup",
            "provider",
            "provider_subject",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String, nullable=False)
    provider_subject = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    user = relationship("User", back_populates="provider_mappings")

    def __repr__(self) -> str:
        return f"<UserProviderMapping user_id={self.user_id} provider={self.provider} sub={self.provider_subject}>"

