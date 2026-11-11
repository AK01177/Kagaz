"""add review comments, decision timestamp, and audit events

Revision ID: a9c3e7f1b204
Revises: f2b8c4d1e9a3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9c3e7f1b204"
down_revision: Union[str, Sequence[str], None] = "f2b8c4d1e9a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("last_decision_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "review_comments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.String(length=36), nullable=False),
        sa.Column("author_role", sa.String(length=64), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_comments_document_id", "review_comments", ["document_id"], unique=False)
    op.create_index("ix_review_comments_organization_id", "review_comments", ["organization_id"], unique=False)
    op.create_index("ix_review_comments_author_id", "review_comments", ["author_id"], unique=False)
    op.create_index("ix_review_comments_doc_created", "review_comments", ["document_id", "created_at"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("actor_role", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=64), nullable=True),
        sa.Column("to_status", sa.String(length=64), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_document_id", "audit_events", ["document_id"], unique=False)
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"], unique=False)
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"], unique=False)
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"], unique=False)
    op.create_index("ix_audit_events_doc_created", "audit_events", ["document_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_events_doc_created", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_id", table_name="audit_events")
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_organization_id", table_name="audit_events")
    op.drop_index("ix_audit_events_document_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_review_comments_doc_created", table_name="review_comments")
    op.drop_index("ix_review_comments_author_id", table_name="review_comments")
    op.drop_index("ix_review_comments_organization_id", table_name="review_comments")
    op.drop_index("ix_review_comments_document_id", table_name="review_comments")
    op.drop_table("review_comments")

    op.drop_column("documents", "last_decision_at")
