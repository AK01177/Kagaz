"""create documents table

Revision ID: 06961ad088b5
Revises:
Create Date: 2026-10-21 17:55:51.425388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "06961ad088b5"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create documents table and indexes."""
    document_status = sa.Enum(
        "UPLOADED",
        "PROCESSING",
        "CLASSIFIED",
        "FAILED",
        name="documentstatus",
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("uploaded_by", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("status", document_status, nullable=False),
        sa.Column("upload_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("classification", sa.String(), nullable=True),
        sa.Column("classification_confidence", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "classification_confidence IS NULL OR (classification_confidence >= 0.0 AND classification_confidence <= 1.0)",
            name="ck_documents_classification_confidence_range",
        ),
        if_not_exists=True,
    )

    op.create_index(
        "ix_documents_organization_id",
        "documents",
        ["organization_id"],
        if_not_exists=True,
    )

    op.create_index(
        "ix_documents_status",
        "documents",
        ["status"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """Drop documents table and indexes."""
    op.drop_index(
        "ix_documents_status",
        table_name="documents",
        if_exists=True,
    )
    op.drop_index(
        "ix_documents_organization_id",
        table_name="documents",
        if_exists=True,
    )
    op.drop_table("documents", if_exists=True)

    bind = op.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS documentstatus"))
