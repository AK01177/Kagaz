"""add document workflow state machine and transition history

Revision ID: f2b8c4d1e9a3
Revises: e1a7c94d2b60
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2b8c4d1e9a3"
down_revision: Union[str, Sequence[str], None] = "e1a7c94d2b60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_DOCUMENT_STATUSES = (
    "EXTRACTED",
    "VALIDATED",
    "REVIEW_REQUIRED",
    "SUBMITTED",
    "IN_REVIEW",
    "CHANGES_REQUESTED",
    "PENDING_APPROVAL",
    "APPROVED",
    "REJECTED",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for status_value in _NEW_DOCUMENT_STATUSES:
            op.execute(f"ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS '{status_value}'")

    op.add_column("documents", sa.Column("assigned_reviewer_id", sa.String(length=36), nullable=True))
    op.add_column("documents", sa.Column("assigned_approver_id", sa.String(length=36), nullable=True))
    op.add_column(
        "documents",
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("documents", sa.Column("workflow_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("last_decision_by", sa.String(length=36), nullable=True))
    op.add_column("documents", sa.Column("last_decision_comment", sa.Text(), nullable=True))

    op.create_index("ix_documents_assigned_reviewer_id", "documents", ["assigned_reviewer_id"], unique=False)
    op.create_index("ix_documents_assigned_approver_id", "documents", ["assigned_approver_id"], unique=False)

    op.create_table(
        "document_transitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=64), nullable=False),
        sa.Column("to_status", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("actor_role", sa.String(length=64), nullable=False),
        sa.Column("assigned_to_id", sa.String(length=36), nullable=True),
        sa.Column("previous_assignee_id", sa.String(length=36), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_transitions_document_id", "document_transitions", ["document_id"], unique=False)
    op.create_index("ix_document_transitions_organization_id", "document_transitions", ["organization_id"], unique=False)
    op.create_index("ix_document_transitions_actor_id", "document_transitions", ["actor_id"], unique=False)
    op.create_index("ix_document_transitions_assigned_to_id", "document_transitions", ["assigned_to_id"], unique=False)
    op.create_index(
        "ix_document_transitions_doc_created",
        "document_transitions",
        ["document_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_transitions_doc_created", table_name="document_transitions")
    op.drop_index("ix_document_transitions_assigned_to_id", table_name="document_transitions")
    op.drop_index("ix_document_transitions_actor_id", table_name="document_transitions")
    op.drop_index("ix_document_transitions_organization_id", table_name="document_transitions")
    op.drop_index("ix_document_transitions_document_id", table_name="document_transitions")
    op.drop_table("document_transitions")

    op.drop_index("ix_documents_assigned_approver_id", table_name="documents")
    op.drop_index("ix_documents_assigned_reviewer_id", table_name="documents")
    op.drop_column("documents", "last_decision_comment")
    op.drop_column("documents", "last_decision_by")
    op.drop_column("documents", "workflow_updated_at")
    op.drop_column("documents", "revision_number")
    op.drop_column("documents", "assigned_approver_id")
    op.drop_column("documents", "assigned_reviewer_id")
    # PostgreSQL enum values are intentionally retained because they cannot be safely removed.
