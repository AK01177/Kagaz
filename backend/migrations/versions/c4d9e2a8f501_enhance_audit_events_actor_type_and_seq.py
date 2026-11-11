"""enhance audit events with actor_type and sequence_no

Revision ID: c4d9e2a8f501
Revises: a9c3e7f1b204
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d9e2a8f501"
down_revision: Union[str, Sequence[str], None] = "a9c3e7f1b204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audit_events",
        sa.Column("actor_type", sa.String(length=16), nullable=False, server_default="USER"),
    )
    op.add_column(
        "audit_events",
        sa.Column("sequence_no", sa.Integer(), nullable=False, server_default="0"),
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "audit_events",
            "actor_id",
            type_=sa.String(length=64),
            existing_type=sa.String(length=36),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "audit_events",
            "actor_id",
            type_=sa.String(length=36),
            existing_type=sa.String(length=64),
        )
    op.drop_column("audit_events", "sequence_no")
    op.drop_column("audit_events", "actor_type")
