"""create organizations users and memberships tables

Revision ID: b83f09a12c44
Revises: 49eecc4be46a
Create Date: 2026-11-07 00:00:00.000000

DB-02: Organization, User, Membership and Role Schema.
Defines persistent multi-tenant identity models with foreign keys,
uniqueness constraints, and indexes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b83f09a12c44"
down_revision: Union[str, Sequence[str], None] = "49eecc4be46a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    membership_role = sa.Enum(
        "SUBMITTER",
        "REVIEWER",
        "APPROVER",
        "ORG_ADMIN",
        "SYSTEM_ADMIN",
        "COMPLIANCE",
        "AUDITOR",
        name="membershiprole",
    )

    # 1. Organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_organizations_slug",
        "organizations",
        ["slug"],
        unique=True,
        if_not_exists=True,
    )

    # 2. Users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("provider_subject", sa.String(), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_users_provider_subject"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        unique=True,
        if_not_exists=True,
    )
    op.create_index(
        "ix_users_provider_subject",
        "users",
        ["provider", "provider_subject"],
        if_not_exists=True,
    )

    # 3. User provider mappings table (explicit external ID provider mapping)
    op.create_table(
        "user_provider_mappings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_subject", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "provider",
            "provider_subject",
            name="uq_user_provider_mappings_provider_subject",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_user_provider_mappings_user_id",
        "user_provider_mappings",
        ["user_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_user_provider_mappings_lookup",
        "user_provider_mappings",
        ["provider", "provider_subject"],
        if_not_exists=True,
    )

    # 4. Memberships table
    op.create_table(
        "memberships",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", membership_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_memberships_org_user",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_memberships_organization_id",
        "memberships",
        ["organization_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_memberships_user_id",
        "memberships",
        ["user_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_memberships_role",
        "memberships",
        ["role"],
        if_not_exists=True,
    )


def downgrade() -> None:
    # Drop in reverse order of creation
    op.drop_index("ix_memberships_role", table_name="memberships", if_exists=True)
    op.drop_index("ix_memberships_user_id", table_name="memberships", if_exists=True)
    op.drop_index("ix_memberships_organization_id", table_name="memberships", if_exists=True)
    op.drop_table("memberships", if_exists=True)

    op.drop_index("ix_user_provider_mappings_lookup", table_name="user_provider_mappings", if_exists=True)
    op.drop_index("ix_user_provider_mappings_user_id", table_name="user_provider_mappings", if_exists=True)
    op.drop_table("user_provider_mappings", if_exists=True)

    op.drop_index("ix_users_provider_subject", table_name="users", if_exists=True)
    op.drop_index("ix_users_email", table_name="users", if_exists=True)
    op.drop_table("users", if_exists=True)

    op.drop_index("ix_organizations_slug", table_name="organizations", if_exists=True)
    op.drop_table("organizations", if_exists=True)

    bind = op.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS membershiprole"))

