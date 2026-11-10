"""Database models for policy management and retrieval."""
import enum
import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


EMBEDDING_DIMENSION = 1536


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PolicyClassification(str, enum.Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    REVIEWER_ONLY = "REVIEWER_ONLY"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class PolicyVersionStatus(str, enum.Enum):
    """Track an ingestion attempt through processing, publication, or failure."""
    PROCESSING = "PROCESSING"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    FAILED = "FAILED"


class Policy(Base):
    __tablename__ = "policies"
    __table_args__ = (
        Index("ix_policies_organization_domain", "organization_id", "domain"),
        CheckConstraint(
            "classification IN ('PUBLIC', 'INTERNAL', 'REVIEWER_ONLY', 'CONFIDENTIAL', 'RESTRICTED')",
            name="ck_policies_classification",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    classification = Column(
        Enum(PolicyClassification),
        nullable=False,
        default=PolicyClassification.INTERNAL,
    )
    domain = Column(String(100), nullable=True, index=True)
    document_type = Column(String(100), nullable=True)
    current_version = Column(String(50), nullable=False, default="v1")
    content = Column(Text, nullable=True)
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


class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint("policy_id", "version", name="uq_policy_versions_policy_version"),
        Index("ix_policy_versions_policy_status", "policy_id", "status"),
        # Enforce one active version at the database layer, including concurrent requests.
        Index(
            "uq_policy_versions_one_active",
            "policy_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    policy_id = Column(
        String(36),
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    version = Column(String(50), nullable=False)
    status = Column(
        Enum(PolicyVersionStatus),
        nullable=False,
        default=PolicyVersionStatus.ARCHIVED,
        index=True,
    )
    published_at = Column(DateTime(timezone=True), nullable=True)
    content = Column(Text, nullable=True)
    changelog = Column(String, nullable=True)
    created_by = Column(String(36), nullable=True)
    ingestion_error = Column(Text, nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    policy = relationship("Policy", back_populates="versions")
    source_document = relationship("Document")
    chunks = relationship(
        "PolicyChunk",
        back_populates="policy_version",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="ck_policy_chunks_chunk_index_nonnegative"),
        CheckConstraint(
            "page_number IS NULL OR page_number >= 1",
            name="ck_policy_chunks_page_number_positive",
        ),
        Index("ix_policy_chunks_policy_version_chunk", "policy_version_id", "chunk_index"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    policy_version_id = Column(
        String(36),
        ForeignKey("policy_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIMENSION), nullable=False)
    page_number = Column(Integer, nullable=True)
    section = Column(String(255), nullable=True)
    chunk_index = Column(Integer, nullable=False)
    chunk_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    policy_version = relationship("PolicyVersion", back_populates="chunks")
