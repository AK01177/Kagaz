"""create organization-scoped policy retrieval tables

Revision ID: 7f2c1a8b4d10
Revises: 49eecc4be46a
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "7f2c1a8b4d10"
down_revision: Union[str, Sequence[str], None] = "49eecc4be46a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    classification = sa.Enum(
        "PUBLIC",
        "INTERNAL",
        "REVIEWER_ONLY",
        "CONFIDENTIAL",
        "RESTRICTED",
        name="policyclassification",
    )
    version_status = sa.Enum(
        "ACTIVE",
        "ARCHIVED",
        name="policyversionstatus",
    )

    op.create_table(
        "policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("classification", classification, nullable=False),
        sa.Column("domain", sa.String(100), nullable=True),
        sa.Column("document_type", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "classification IN ('PUBLIC', 'INTERNAL', 'REVIEWER_ONLY', 'CONFIDENTIAL', 'RESTRICTED')",
            name="ck_policies_classification",
        ),
    )
    op.create_index("ix_policies_organization_id", "policies", ["organization_id"])
    op.create_index(
        "ix_policies_organization_domain",
        "policies",
        ["organization_id", "domain"],
    )

    op.create_table(
        "policy_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "policy_id",
            sa.String(36),
            sa.ForeignKey("policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("status", version_status, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("policy_id", "version", name="uq_policy_versions_policy_version"),
    )
    op.create_index("ix_policy_versions_policy_id", "policy_versions", ["policy_id"])
    op.create_index(
        "ix_policy_versions_source_document_id",
        "policy_versions",
        ["source_document_id"],
    )
    op.create_index("ix_policy_versions_status", "policy_versions", ["status"])
    op.create_index(
        "ix_policy_versions_policy_status",
        "policy_versions",
        ["policy_id", "status"],
    )
    if bind.dialect.name == "postgresql":
        op.create_index(
            "uq_policy_versions_one_active",
            "policy_versions",
            ["policy_id"],
            unique=True,
            postgresql_where=sa.text("status = 'ACTIVE'"),
        )
        op.execute(
            "CREATE INDEX ix_policy_chunks_embedding "
            "ON policy_chunks USING hnsw (embedding vector_cosine_ops)"
        )

    op.create_table(
        "policy_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "policy_version_id",
            sa.String(36),
            sa.ForeignKey("policy_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(255), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name="ck_policy_chunks_chunk_index_nonnegative",
        ),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number >= 1",
            name="ck_policy_chunks_page_number_positive",
        ),
    )
    op.create_index("ix_policy_chunks_policy_version_id", "policy_chunks", ["policy_version_id"])
    op.create_index(
        "ix_policy_chunks_policy_version_chunk",
        "policy_chunks",
        ["policy_version_id", "chunk_index"],
    )


def downgrade() -> None:
    op.drop_index("ix_policy_chunks_policy_version_chunk", table_name="policy_chunks")
    op.drop_index("ix_policy_chunks_policy_version_id", table_name="policy_chunks")
    op.drop_table("policy_chunks")
    op.drop_index("ix_policy_versions_policy_status", table_name="policy_versions")
    op.drop_index("ix_policy_versions_status", table_name="policy_versions")
    op.drop_index("ix_policy_versions_source_document_id", table_name="policy_versions")
    op.drop_index("ix_policy_versions_policy_id", table_name="policy_versions")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_policy_chunks_embedding")
        op.drop_index("uq_policy_versions_one_active", table_name="policy_versions")
    op.drop_table("policy_versions")
    op.drop_index("ix_policies_organization_domain", table_name="policies")
    op.drop_index("ix_policies_organization_id", table_name="policies")
    op.drop_table("policies")
