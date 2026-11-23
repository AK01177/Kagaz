"""Store document processing metadata in the database.

Previously it lived in a JSON file next to the uploaded file, which is lost when the
server's disk is wiped (e.g. on a redeploy). Existing rows keep NULL and fall back to the
file if one exists.

Revision ID: c7a3d9e1f452
Revises: b2d5e8f1a306
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7a3d9e1f452"
down_revision: Union[str, None] = "b2d5e8f1a306"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("metadata_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "metadata_json")
