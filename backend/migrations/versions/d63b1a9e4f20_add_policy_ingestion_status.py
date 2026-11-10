"""add policy ingestion lifecycle fields

Revision ID: d63b1a9e4f20
Revises: c4e8f1a2b7d9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d63b1a9e4f20"
down_revision: Union[str, Sequence[str], None] = "c4e8f1a2b7d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # PostgreSQL stores these statuses in a native enum created by the prior migration.
        op.execute("ALTER TYPE policyversionstatus ADD VALUE IF NOT EXISTS 'PROCESSING'")
        op.execute("ALTER TYPE policyversionstatus ADD VALUE IF NOT EXISTS 'FAILED'")

    op.add_column("policy_versions", sa.Column("ingestion_error", sa.Text(), nullable=True))
    op.add_column(
        "policy_versions",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    if bind.dialect.name == "sqlite":
        # The initial migration only creates this partial index on PostgreSQL.
        op.create_index(
            "uq_policy_versions_one_active",
            "policy_versions",
            ["policy_id"],
            unique=True,
            sqlite_where=sa.text("status = 'ACTIVE'"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.drop_index("uq_policy_versions_one_active", table_name="policy_versions")
    op.drop_column("policy_versions", "finished_at")
    op.drop_column("policy_versions", "ingestion_error")
    # PostgreSQL enum values are intentionally retained because they cannot be safely removed.
    # PostgreSQL does not support safely removing values from an enum type.
