"""Bring policy tables in line with the models and track embedding metadata.

Two parts:

1. Catch-up. The Policy / PolicyVersion models gained columns for the text-based policy
   API (description, current_version, content, is_active, ...) that no earlier migration
   created, and `policy_versions.source_document_id` is NOT NULL although text policies
   have no source file. Databases created only from migrations therefore failed on every
   policy query.
2. RAG metadata: which embedding model produced each version's vectors (vectors from
   different models are not comparable) and a content hash per chunk (lets a new
   version reuse the vector of an unchanged clause).

Existing rows stay valid: new NOT NULL columns have server defaults. Existing chunks have
no `embedding_model`, so retrieval ignores them until their policy is re-indexed
(`python -m scripts.reindex_policies`).

Revision ID: b2d5e8f1a306
Revises: 6a4b9d2e7c31
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2d5e8f1a306"
down_revision: Union[str, None] = "6a4b9d2e7c31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- policies -----------------------------------------------------------------------
    op.add_column("policies", sa.Column("description", sa.String(), nullable=True))
    op.add_column(
        "policies",
        sa.Column("current_version", sa.String(length=50), nullable=False, server_default="v1"),
    )
    op.add_column("policies", sa.Column("content", sa.Text(), nullable=True))
    op.add_column(
        "policies",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("policies", sa.Column("created_by", sa.String(length=36), nullable=True))
    op.add_column(
        "policies",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # --- policy_versions ----------------------------------------------------------------
    op.add_column("policy_versions", sa.Column("content", sa.Text(), nullable=True))
    op.add_column("policy_versions", sa.Column("changelog", sa.String(), nullable=True))
    op.add_column("policy_versions", sa.Column("created_by", sa.String(length=36), nullable=True))
    op.add_column("policy_versions", sa.Column("embedding_model", sa.String(length=100), nullable=True))
    with op.batch_alter_table("policy_versions") as batch:
        batch.alter_column("source_document_id", existing_type=sa.String(length=36), nullable=True)

    # --- policy_chunks ------------------------------------------------------------------
    op.add_column("policy_chunks", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_policy_chunks_content_hash", "policy_chunks", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_policy_chunks_content_hash", table_name="policy_chunks")
    op.drop_column("policy_chunks", "content_hash")

    # source_document_id is left nullable: restoring NOT NULL would fail once text policies exist.
    for column in ("embedding_model", "created_by", "changelog", "content"):
        op.drop_column("policy_versions", column)

    for column in ("updated_at", "created_by", "is_active", "content", "current_version", "description"):
        op.drop_column("policies", column)
