"""merge policy retrieval and identity migration heads

Revision ID: c4e8f1a2b7d9
Revises: 7f2c1a8b4d10, b83f09a12c44
"""
from typing import Sequence, Union


revision: str = "c4e8f1a2b7d9"
down_revision: Union[str, Sequence[str], None] = (
    "7f2c1a8b4d10",
    "b83f09a12c44",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
