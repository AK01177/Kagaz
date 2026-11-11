"""create notifications table for in-app workflow notifications

Revision ID: b7e2d4a1c905
Revises: c4d9e2a8f501
Create Date: 2026-11-11 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7e2d4a1c905"
down_revision: Union[str, Sequence[str], None] = "c4d9e2a8f501"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("recipient_user_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("notification_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_notifications_idempotency_key"),
        if_not_exists=True,
    )

    op.create_index(
        "ix_notifications_recipient_read",
        "notifications",
        ["recipient_user_id", "is_read"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_notifications_organization_id",
        "notifications",
        ["organization_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_notifications_created_at",
        "notifications",
        ["created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_notifications_document_id",
        "notifications",
        ["document_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_document_id", table_name="notifications", if_exists=True)
    op.drop_index("ix_notifications_created_at", table_name="notifications", if_exists=True)
    op.drop_index("ix_notifications_organization_id", table_name="notifications", if_exists=True)
    op.drop_index("ix_notifications_recipient_read", table_name="notifications", if_exists=True)
    op.drop_table("notifications", if_exists=True)
