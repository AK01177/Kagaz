"""Create validation result records used by document review.

Revision ID: 6a4b9d2e7c31
Revises: 34d0c81a9f22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6a4b9d2e7c31"
down_revision: Union[str, None] = "34d0c81a9f22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "validation_results",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "policy_id",
            sa.String(length=36),
            sa.ForeignKey("policies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("policy_version", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("validated_by", sa.String(length=36), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_validation_results_document_id", "validation_results", ["document_id"], unique=True
    )
    op.create_index(
        "ix_validation_results_organization_id", "validation_results", ["organization_id"]
    )
    op.create_index("ix_validation_results_policy_id", "validation_results", ["policy_id"])


def downgrade() -> None:
    op.drop_index("ix_validation_results_policy_id", table_name="validation_results")
    op.drop_index("ix_validation_results_organization_id", table_name="validation_results")
    op.drop_index("ix_validation_results_document_id", table_name="validation_results")
    op.drop_table("validation_results")
