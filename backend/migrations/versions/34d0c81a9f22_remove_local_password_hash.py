"""Remove local password hashes after moving auth to Supabase.

Revision ID: 34d0c81a9f22
Revises: 8f3a1c2d9e40
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "34d0c81a9f22"
down_revision: Union[str, None] = "8f3a1c2d9e40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "password_hash")


def downgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))
