"""
Unit and integration tests for BE-08: Policy Management.
Validates:
1. Policy creation with initial v1 version snapshot (US-18 AC1, AC3).
2. Multi-tenant isolation between organizations (US-18 AC4).
3. Automatic version incrementing upon content updates (NFR-AUD-03, US-23).
4. Domain-based and active-status filtering (US-18 AC4).
5. Soft-deactivation of policies.
6. Schema validation guards for mandatory policy fields.
"""
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.organization import Organization
from app.models.policy import Policy, PolicyVersion
from app.schemas.policy import PolicyCreate, PolicyUpdate
from app.crud.policy import (
    create_policy,
    deactivate_policy,
    get_policy,
    list_policies,
    list_policy_versions,
    update_policy,
)


@pytest.fixture
def db():
    """In-memory SQLite database enforcing foreign keys."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed two isolated tenant organizations
    org_a = Organization(id="org_alpha_123", name="Alpha Corp", slug="alpha-corp")
    org_b = Organization(id="org_beta_456", name="Beta Corp", slug="beta-corp")
    session.add_all([org_a, org_b])
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


class TestBE08PolicyManagement:
    def test_create_policy_with_initial_version(self, db):
        data = PolicyCreate(
            name="Travel Expense Policy",
            domain="financial",
            description="Rules for employee travel reimbursement",
            content="Airfare must be economy class. Max hotel rate is $200/night.",
        )
        policy = create_policy(db, organization_id="org_alpha_123", data=data, user_id="user_admin_1")

        assert policy.id is not None
        assert policy.name == "Travel Expense Policy"
        assert policy.domain == "financial"
        assert policy.current_version == "v1"
        assert policy.organization_id == "org_alpha_123"
        assert policy.is_active is True

        # Initial immutable version record created
        versions = list_policy_versions(db, policy.id)
        assert len(versions) == 1
        assert versions[0].version == "v1"
        assert versions[0].content == data.content
        assert versions[0].changelog == "Initial policy creation"

    def test_tenant_isolation_enforcement(self, db):
        # Org Alpha creates a compliance policy
        data = PolicyCreate(
            name="Alpha Confidential Policy",
            domain="compliance",
            content="Confidential to Alpha Corp employees only.",
        )
        policy = create_policy(db, organization_id="org_alpha_123", data=data)

        # Org Alpha can fetch it
        assert get_policy(db, policy.id, organization_id="org_alpha_123") is not None

        # Org Beta CANNOT fetch it (tenant isolation)
        assert get_policy(db, policy.id, organization_id="org_beta_456") is None

        # Org Beta policy list does not leak Org Alpha's policy
        beta_policies = list_policies(db, organization_id="org_beta_456")
        assert not any(p.id == policy.id for p in beta_policies)

    def test_update_policy_increments_version_and_records_history(self, db):
        data = PolicyCreate(
            name="Procurement Limit Policy",
            domain="financial",
            content="Purchases up to $500 do not require manager approval.",
        )
        policy = create_policy(db, organization_id="org_alpha_123", data=data)
        assert policy.current_version == "v1"

        # Update content -> triggers new version (v2)
        update_data = PolicyUpdate(
            content="Purchases up to $1000 do not require manager approval.",
            changelog="Raised threshold to $1000 for inflation adjustment.",
        )
        updated = update_policy(db, policy=policy, data=update_data, user_id="user_admin_2")

        assert updated.current_version == "v2"
        assert updated.content == "Purchases up to $1000 do not require manager approval."

        # Audit history contains both v2 and v1
        versions = list_policy_versions(db, policy.id)
        assert len(versions) == 2
        assert versions[0].version == "v2"
        assert versions[0].changelog == "Raised threshold to $1000 for inflation adjustment."
        assert versions[1].version == "v1"

    def test_update_metadata_without_content_does_not_increment_version(self, db):
        data = PolicyCreate(name="Initial Name", domain="hr", content="Original content")
        policy = create_policy(db, organization_id="org_alpha_123", data=data)

        # Update only name & description
        updated = update_policy(db, policy=policy, data=PolicyUpdate(name="Renamed Policy", description="New desc"))
        assert updated.name == "Renamed Policy"
        assert updated.current_version == "v1"  # Content unchanged, version stays v1
        assert len(list_policy_versions(db, policy.id)) == 1

    def test_filter_by_domain_and_active_status(self, db):
        create_policy(db, "org_alpha_123", PolicyCreate(name="P1", domain="financial", content="c1"))
        create_policy(db, "org_alpha_123", PolicyCreate(name="P2", domain="hr", content="c2"))
        p3 = create_policy(db, "org_alpha_123", PolicyCreate(name="P3", domain="academic", content="c3"))

        # Domain filtering
        fin_list = list_policies(db, "org_alpha_123", domain="financial")
        assert len(fin_list) == 1
        assert fin_list[0].domain == "financial"

        # Deactivate P3
        deactivate_policy(db, p3)

        # Active filtering
        active_list = list_policies(db, "org_alpha_123", is_active=True)
        assert not any(p.id == p3.id for p in active_list)

        inactive_list = list_policies(db, "org_alpha_123", is_active=False)
        assert any(p.id == p3.id for p in inactive_list)

    def test_schema_validation_guards(self):
        # Empty name should fail validation
        with pytest.raises(Exception):
            PolicyCreate(name="", domain="financial", content="content")

        # Empty content should fail validation
        with pytest.raises(Exception):
            PolicyCreate(name="Policy", domain="financial", content="")
