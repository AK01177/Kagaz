"""Which policies apply to a document: type spellings, policies for every type, domains (RAG Phase 3)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.policy import Policy, PolicyChunk, PolicyVersion, PolicyVersionStatus
from services.policy_retrieval import PolicyScope, _chunk_query
from tests.test_policy_access_scope import ZERO_VECTOR


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


def add_policy(db, name, document_type=None, domain=None):
    policy = Policy(organization_id="org-a", name=name, document_type=document_type, domain=domain)
    db.add(policy)
    db.flush()
    version = PolicyVersion(policy_id=policy.id, version="v1", status=PolicyVersionStatus.ACTIVE)
    db.add(version)
    db.flush()
    db.add(PolicyChunk(
        policy_version_id=version.id, content=name, embedding=ZERO_VECTOR, chunk_index=0, chunk_metadata={},
    ))
    db.flush()


def visible(db, **scope_fields) -> set[str]:
    scope = PolicyScope("org-a", "ORG_ADMIN", **scope_fields)
    return {name for (name,) in _chunk_query(db, scope, Policy.name).distinct().all()}


@pytest.fixture
def policies(db):
    add_policy(db, "Stored canonical", "financial")
    add_policy(db, "Stored as invoice", "invoice")
    add_policy(db, "Stored messy", " Expense-Claim ")
    add_policy(db, "For every type", None)
    add_policy(db, "HR only", "hr_documents")
    add_policy(db, "Academic only", "academics")


@pytest.mark.parametrize("asking", ["financial", "Invoice", "INVOICES", "purchase order"])
def test_a_document_sees_policies_for_its_type_in_any_spelling_plus_policies_for_every_type(db, policies, asking):
    assert visible(db, document_type=asking) == {
        "Stored canonical", "Stored as invoice", "Stored messy", "For every type",
    }


def test_policies_for_other_types_are_not_applied(db, policies):
    assert visible(db, document_type="HR Forms") == {"HR only", "For every type"}
    assert visible(db, document_type="transcript") == {"Academic only", "For every type"}


def test_with_no_type_given_every_policy_is_searchable_unless_strict(db, policies):
    assert len(visible(db)) == 6
    # Validating a document that was never classified: only policies for every type can apply.
    assert visible(db, strict_untyped=True) == {"For every type"}


def test_an_unknown_type_in_the_request_only_matches_policies_for_every_type(db, policies):
    assert visible(db, document_type="memo") == {"For every type"}


def test_domain_matching_ignores_case(db):
    add_policy(db, "Finance rules", domain="Finance")
    add_policy(db, "HR rules", domain="hr")
    assert visible(db, domain="FINANCE") == {"Finance rules"}
    assert visible(db, domain=" hr ") == {"HR rules"}
