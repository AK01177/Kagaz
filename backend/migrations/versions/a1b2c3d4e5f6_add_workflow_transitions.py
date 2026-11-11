"""add workflow transitions and extend document status

Revision ID: a1b2c3d4e5f6
Revises: e1a7c94d2b60
Create Date: 2026-11-11 14:00:00.000000

BE-10: Adds workflow_transitions table and extends the documentstatus enum
with the five new states required for the human review lifecycle:
  PENDING_REVIEW, UNDER_REVIEW, CHANGES_REQUESTED, APPROVED, REJECTED

Also adds the `assigned_reviewer` column to the documents table so the
currently-assigned reviewer can be queried without a JOIN.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e1a7c94d2b60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind is not None and bind.dialect.name == "postgresql"

    # ------------------------------------------------------------------
    # 1. Extend the documentstatus enum (PostgreSQL ALTER TYPE)
    # ------------------------------------------------------------------
    if is_pg:
        for new_value in (
            "PENDING_REVIEW",
            "UNDER_REVIEW",
            "CHANGES_REQUESTED",
            "APPROVED",
            "REJECTED",
        ):
            op.execute(
                sa.text(f"ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS '{new_value}'")
            )
    # SQLite uses VARCHAR for enums so no DDL change is needed there.

    # ------------------------------------------------------------------
    # 2. Add assigned_reviewer column to documents
    # ------------------------------------------------------------------
    op.add_column(
        "documents",
        sa.Column("assigned_reviewer", sa.String(length=36), nullable=True),
        schema=None,
    )

    # ------------------------------------------------------------------
    # 3. Create workflow_transitions table
    # ------------------------------------------------------------------
    workflow_action = sa.Enum(
        "SUBMIT",
        "ASSIGN",
        "REQUEST_CHANGES",
        "RESUBMIT",
        "APPROVE",
        "REJECT",
        name="workflowaction",
    )

    op.create_table(
        "workflow_transitions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("actor_role", sa.String(length=50), nullable=False),
        sa.Column("action", workflow_action, nullable=False),
        sa.Column("from_status", sa.String(length=50), nullable=False),
        sa.Column("to_status", sa.String(length=50), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("assigned_to", sa.String(length=36), nullable=True),
        sa.Column("transitioned_at", sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )

    op.create_index(
        "ix_workflow_transitions_document_id",
        "workflow_transitions",
        ["document_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_workflow_transitions_organization_id",
        "workflow_transitions",
        ["organization_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_workflow_transitions_actor_id",
        "workflow_transitions",
        ["actor_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_transitions_actor_id", table_name="workflow_transitions", if_exists=True)
    op.drop_index("ix_workflow_transitions_organization_id", table_name="workflow_transitions", if_exists=True)
    op.drop_index("ix_workflow_transitions_document_id", table_name="workflow_transitions", if_exists=True)
    op.drop_table("workflow_transitions", if_exists=True)

    op.drop_column("documents", "assigned_reviewer")

    bind = op.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS workflowaction"))
        # Note: PostgreSQL does not support DROP VALUE from an enum type.
        # The extended documentstatus values are retained to avoid data loss.
