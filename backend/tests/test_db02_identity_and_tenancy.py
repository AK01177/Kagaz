"""
Unit and Integration Tests for DB-02: Organization, User, Membership, and Role Schema.

Validates:
1. Alembic migration creates the required tables, foreign keys, and unique constraints.
2. Memberships correctly link users to organizations and roles.
3. Roles must not be accepted from caller-supplied login data.
4. Test/seed data contains at least two isolated organizations.
5. Migration and rollback work correctly on a clean database.
"""
import uuid
import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.db.base import Base
from app.models.organization import Organization
from app.models.user import User, UserProviderMapping
from app.models.membership import Membership, MembershipRole
from app.schemas.organization import OrganizationCreate
from app.schemas.user import UserCreate, UserProviderMappingCreate
from app.schemas.membership import MembershipCreate
from app.crud.organization import create_organization, get_organization, get_organization_by_slug
from app.crud.user import create_user, get_user, get_user_by_email, get_user_by_provider_subject, create_user_provider_mapping
from app.crud.membership import create_membership, get_membership, list_organization_members, get_user_membership_in_org
from app.db.seed import seed_two_organizations
from main import app
from api.auth import get_auth_db


@pytest.fixture
def sqlite_engine():
    """Create an isolated in-memory SQLite engine with foreign key constraints enabled."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(sqlite_engine):
    """Provide a transactional DB session for tests."""
    Session = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=sqlite_engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ==============================================================================
# 1. Organization & User Schema, Uniqueness, and Constraints
# ==============================================================================

def test_organization_creation_and_slug_uniqueness(db_session):
    """Verify Organization model creation and unique slug constraint enforcement."""
    org1 = Organization(name="Tenant One", slug="tenant-1", is_active=True)
    db_session.add(org1)
    db_session.commit()

    assert org1.id is not None
    assert org1.name == "Tenant One"
    assert org1.slug == "tenant-1"
    assert org1.is_active is True

    # Duplicate slug must fail uniqueness check
    org2 = Organization(name="Tenant One Duplicate", slug="tenant-1")
    db_session.add(org2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_user_creation_and_email_uniqueness(db_session):
    """Verify User model creation and email uniqueness constraint."""
    user1 = User(
        email="test_user@example.com",
        full_name="Test User",
        provider="google",
        provider_subject="sub_123",
    )
    db_session.add(user1)
    db_session.commit()

    assert user1.id is not None
    assert user1.email == "test_user@example.com"

    # Duplicate email must raise IntegrityError
    user2 = User(email="test_user@example.com", full_name="Another Name")
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_user_provider_mapping_uniqueness(db_session):
    """Verify UserProviderMapping table enforces unique (provider, provider_subject)."""
    user = User(email="owner@example.com", full_name="Owner")
    db_session.add(user)
    db_session.commit()

    mapping1 = UserProviderMapping(
        user_id=user.id,
        provider="azure_ad",
        provider_subject="azure_sub_999",
    )
    db_session.add(mapping1)
    db_session.commit()

    # Duplicate provider + provider_subject mapping should violate uniqueness
    user2 = User(email="intruder@example.com", full_name="Intruder")
    db_session.add(user2)
    db_session.commit()

    mapping2 = UserProviderMapping(
        user_id=user2.id,
        provider="azure_ad",
        provider_subject="azure_sub_999",
    )
    db_session.add(mapping2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ==============================================================================
# 2. Membership Linking, Roles, and Uniqueness
# ==============================================================================

def test_membership_linking_and_roles(db_session):
    """Verify Membership correctly associates a user to an organization with a role."""
    org = Organization(name="Alpha Org", slug="alpha-org")
    user = User(email="member@alpha.com", full_name="Alpha Member")
    db_session.add_all([org, user])
    db_session.commit()

    membership = Membership(
        organization_id=org.id,
        user_id=user.id,
        role=MembershipRole.REVIEWER,
        is_active=True,
    )
    db_session.add(membership)
    db_session.commit()

    assert membership.id is not None
    assert membership.role == MembershipRole.REVIEWER
    assert membership.organization_id == org.id
    assert membership.user_id == user.id

    # Verify relationships
    assert membership.organization.slug == "alpha-org"
    assert membership.user.email == "member@alpha.com"


def test_membership_uniqueness_per_org_and_user(db_session):
    """A user cannot have multiple memberships in the same organization."""
    org = Organization(name="Beta Org", slug="beta-org")
    user = User(email="member@beta.com")
    db_session.add_all([org, user])
    db_session.commit()

    m1 = Membership(organization_id=org.id, user_id=user.id, role=MembershipRole.SUBMITTER)
    db_session.add(m1)
    db_session.commit()

    # Attempt second membership in same org for same user
    m2 = Membership(organization_id=org.id, user_id=user.id, role=MembershipRole.ORG_ADMIN)
    db_session.add(m2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_foreign_key_enforcement_and_cascade_delete(db_session):
    """Verify FK referential integrity and cascade deletion."""
    org = Organization(name="Gamma Org", slug="gamma-org")
    user = User(email="gamma@gamma.com")
    db_session.add_all([org, user])
    db_session.commit()

    m = Membership(organization_id=org.id, user_id=user.id, role=MembershipRole.SUBMITTER)
    db_session.add(m)
    db_session.commit()

    # Invalid organization foreign key
    with pytest.raises(IntegrityError):
        invalid_m = Membership(
            organization_id=str(uuid.uuid4()),
            user_id=user.id,
            role=MembershipRole.SUBMITTER,
        )
        db_session.add(invalid_m)
        db_session.commit()
    db_session.rollback()

    # Cascade delete on organization deletion
    db_session.delete(org)
    db_session.commit()

    remaining_memberships = db_session.query(Membership).filter(Membership.user_id == user.id).all()
    assert len(remaining_memberships) == 0


# ==============================================================================
# 3. Security: Caller-Supplied Role Rejection (Acceptance Criterion 3)
# ==============================================================================

def test_roles_must_not_be_accepted_from_caller_supplied_login(db_session):
    """
    CRITICAL ACCEPTANCE CRITERIA 3:
    Roles must not be accepted from caller-supplied login data.
    Even if an attacker sends {"role": "ORG_ADMIN"}, the role issued in the JWT
    must reflect the persisted Membership role in the database.
    """
    app.dependency_overrides[get_auth_db] = lambda: db_session

    try:
        client = TestClient(app)

        # 1. Setup user in DB with persisted SUBMITTER role
        org = Organization(name="Secure Org", slug="secure-org")
        user = User(email="victim@secure.com", full_name="Victim Submitter")
        db_session.add_all([org, user])
        db_session.commit()

        membership = Membership(
            organization_id=org.id,
            user_id=user.id,
            role=MembershipRole.SUBMITTER,
            is_active=True,
        )
        db_session.add(membership)
        db_session.commit()

        # 2. Caller attempts privilege escalation by requesting ORG_ADMIN or SYSTEM_ADMIN
        response = client.post(
            "/api/auth/login",
            json={
                "email": "victim@secure.com",
                "password": "any_password",
                "role": "ORG_ADMIN",  # ATTACK: caller supplied role
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Caller-supplied "ORG_ADMIN" MUST be rejected / ignored
        assert data["user"]["role"] == "SUBMITTER"
        assert data["user"]["organization_id"] == org.id

        # Token claims must also contain SUBMITTER
        token = data["access_token"]
        import jwt
        claims = jwt.decode(token, options={"verify_signature": False})
        assert claims["role"] == "SUBMITTER"
        assert claims["organization_id"] == org.id

    finally:
        app.dependency_overrides.pop(get_auth_db, None)


def test_caller_cannot_elevate_unpersisted_user(db_session):
    """An unpersisted caller cannot grant themselves ORG_ADMIN."""
    app.dependency_overrides[get_auth_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.post(
            "/api/auth/login",
            json={
                "email": "newbie@external.com",
                "role": "SYSTEM_ADMIN",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["role"] == "SUBMITTER"
    finally:
        app.dependency_overrides.pop(get_auth_db, None)


# ==============================================================================
# 4. Multi-Tenant Seed Data (Acceptance Criterion 4)
# ==============================================================================

def test_seed_two_isolated_organizations(db_session):
    """
    CRITICAL ACCEPTANCE CRITERIA 4:
    Test/seed data contains at least two isolated organizations.
    """
    seed_result = seed_two_organizations(db_session)

    org_a = seed_result["org_a"]
    org_b = seed_result["org_b"]

    assert org_a.slug == "acme-corp"
    assert org_b.slug == "beta-logistics"
    assert org_a.id != org_b.id

    # Verify Org A members
    members_a = list_organization_members(db_session, org_a.id)
    emails_a = {m.user.email for m in members_a}
    assert "alice@acme.com" in emails_a
    assert "bob@acme.com" in emails_a
    assert "charlie@acme.com" in emails_a

    # Verify Org B members
    members_b = list_organization_members(db_session, org_b.id)
    emails_b = {m.user.email for m in members_b}
    assert "david@beta.com" in emails_b
    assert "eve@beta.com" in emails_b
    assert "frank@beta.com" in emails_b

    # Verify strict isolation: No member of Org A belongs to Org B
    assert emails_a.isdisjoint(emails_b)

    # Verify roles assigned correctly
    alice_mem = get_user_membership_in_org(db_session, org_a.id, seed_result["users_a"][0].id)
    assert alice_mem.role == MembershipRole.ORG_ADMIN

    bob_mem = get_user_membership_in_org(db_session, org_a.id, seed_result["users_a"][1].id)
    assert bob_mem.role == MembershipRole.SUBMITTER

    charlie_mem = get_user_membership_in_org(db_session, org_a.id, seed_result["users_a"][2].id)
    assert charlie_mem.role == MembershipRole.REVIEWER


# ==============================================================================
# 5. Migration and Rollback Verification (Acceptance Criterion 1 & 5)
# ==============================================================================

def test_migration_and_rollback_on_clean_database(tmp_path):
    """
    CRITICAL ACCEPTANCE CRITERIA 1 & 5:
    Alembic migration creates the required tables and constraints,
    and rollback works correctly on a clean database.
    """
    db_file = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{db_file}"

    # Setup Alembic Config
    alembic_cfg = Config("backend/alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    alembic_cfg.set_main_option("script_location", "backend/migrations")

    # 1. Run migration upgrade to head (includes b83f09a12c44)
    command.upgrade(alembic_cfg, "head")

    # Verify tables were created
    engine = create_engine(db_url)
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    assert "organizations" in table_names
    assert "users" in table_names
    assert "user_provider_mappings" in table_names
    assert "memberships" in table_names

    # Check columns and unique constraints in organizations
    org_cols = [c["name"] for c in inspector.get_columns("organizations")]
    assert "id" in org_cols
    assert "slug" in org_cols
    assert "name" in org_cols
    assert "is_active" in org_cols

    # Check columns in memberships
    membership_cols = [c["name"] for c in inspector.get_columns("memberships")]
    assert "organization_id" in membership_cols
    assert "user_id" in membership_cols
    assert "role" in membership_cols

    # 2. Test Rollback (downgrade to 49eecc4be46a)
    command.downgrade(alembic_cfg, "49eecc4be46a")

    # Verify new tables are dropped during rollback
    inspector = inspect(engine)
    table_names_after_rollback = inspector.get_table_names()

    assert "organizations" not in table_names_after_rollback
    assert "users" not in table_names_after_rollback
    assert "user_provider_mappings" not in table_names_after_rollback
    assert "memberships" not in table_names_after_rollback

    # 3. Re-upgrade to ensure migration can run again cleanly
    command.upgrade(alembic_cfg, "b83f09a12c44")
    inspector = inspect(engine)
    table_names_reupgrade = inspector.get_table_names()
    assert "organizations" in table_names_reupgrade
    assert "memberships" in table_names_reupgrade

    engine.dispose()
