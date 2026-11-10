"""add persisted policy validation runs and findings

Revision ID: e1a7c94d2b60
Revises: d63b1a9e4f20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1a7c94d2b60"
down_revision: Union[str, Sequence[str], None] = "d63b1a9e4f20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_validation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("requested_by", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("retrieval_outcome", sa.String(length=32), nullable=False),
        sa.Column("policy_versions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policy_validation_runs_document_id", "policy_validation_runs", ["document_id"])
    op.create_index("ix_policy_validation_runs_organization_id", "policy_validation_runs", ["organization_id"])
    op.create_table(
        "policy_validation_findings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("policy_validation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requirement", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=True),
        sa.Column("document_value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_references", sa.JSON(), nullable=False),
    )
    op.create_index("ix_policy_validation_findings_run_id", "policy_validation_findings", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_policy_validation_findings_run_id", table_name="policy_validation_findings")
    op.drop_table("policy_validation_findings")
    op.drop_index("ix_policy_validation_runs_organization_id", table_name="policy_validation_runs")
    op.drop_index("ix_policy_validation_runs_document_id", table_name="policy_validation_runs")
    op.drop_table("policy_validation_runs")
