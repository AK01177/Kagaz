"""create extractions table

Revision ID: 49eecc4be46a
Revises: 06961ad088b5
Create Date: 2026-10-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "49eecc4be46a"
down_revision: Union[str, Sequence[str], None] = "06961ad088b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "extractions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_extractions_confidence_range",
        ),
        sa.UniqueConstraint(
            "document_id",
            "field_name",
            name="uq_extractions_document_field",
        ),
        if_not_exists=True,
    )

    op.create_index(
        "ix_extractions_document_id",
        "extractions",
        ["document_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_extractions_document_id",
        table_name="extractions",
        if_exists=True,
    )
    op.drop_table("extractions", if_exists=True)

