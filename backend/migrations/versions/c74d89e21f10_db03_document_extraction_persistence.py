"""integrate document extraction persistence

Revision ID: c74d89e21f10
Revises: b83f09a12c44
Create Date: 2026-11-07 16:00:00.000000

DB-03: PostgreSQL Document and Extraction Persistence Integration.
Persists document lifecycle states (including EXTRACTED), processing timestamps,
and extraction runs establishing the Document -> Extraction Run -> Extracted Fields hierarchy.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c74d89e21f10"
down_revision: Union[str, Sequence[str], None] = "b83f09a12c44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind is not None and bind.dialect.name == "postgresql"

    # 1. Update documentstatus enum in PostgreSQL to add EXTRACTED
    if is_postgres:
        op.execute("ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS 'EXTRACTED'")

    # 2. Add updated_at and processed_at columns to documents table
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch_op.add_column(
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True)
        )

    # 3. Create extractionstatus enum and extraction_runs table
    extraction_status = sa.Enum(
        "PENDING",
        "PROCESSING",
        "SUCCESS",
        "FAILED",
        name="extractionstatus",
    )

    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", extraction_status, nullable=False),
        sa.Column("document_type", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_extraction_runs_document_id",
        "extraction_runs",
        ["document_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_extraction_runs_status",
        "extraction_runs",
        ["status"],
        if_not_exists=True,
    )

    # 4. Add extraction_run_id column and foreign key to extractions table
    with op.batch_alter_table("extractions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "extraction_run_id",
                sa.String(length=36),
                sa.ForeignKey(
                    "extraction_runs.id",
                    ondelete="CASCADE",
                    name="fk_extractions_extraction_run_id",
                ),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_extractions_extraction_run_id",
            ["extraction_run_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind is not None and bind.dialect.name == "postgresql"

    # 1. Drop foreign key and column from extractions
    with op.batch_alter_table("extractions") as batch_op:
        batch_op.drop_index("ix_extractions_extraction_run_id")
        batch_op.drop_column("extraction_run_id")

    # 2. Drop extraction_runs table and indexes
    op.drop_index(
        "ix_extraction_runs_status",
        table_name="extraction_runs",
        if_exists=True,
    )
    op.drop_index(
        "ix_extraction_runs_document_id",
        table_name="extraction_runs",
        if_exists=True,
    )
    op.drop_table("extraction_runs", if_exists=True)

    if is_postgres:
        op.execute(sa.text("DROP TYPE IF EXISTS extractionstatus"))

    # 3. Drop columns from documents table
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("processed_at")
        batch_op.drop_column("updated_at")
