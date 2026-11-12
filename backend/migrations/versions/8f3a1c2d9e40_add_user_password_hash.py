"""Add password_hash column to users table.

Revision ID: 8f3a1c2d9e40
Revises: b7e2d4a1c905
Create Date: 2026-11-11 20:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f3a1c2d9e40"
down_revision: Union[str, Sequence[str], None] = "b7e2d4a1c905"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable password_hash column for local credential verification."""
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove password_hash column from users."""
    op.drop_column("users", "password_hash")
