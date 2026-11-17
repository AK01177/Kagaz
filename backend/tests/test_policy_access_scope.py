"""Access rules shared by every policy search path (RAG Phase 1).

Runs on in-memory SQLite: it covers the filter rules and the keyword fallback, which
need no pgvector operators. Vector ranking is covered by test_qa10_policy_retrieval.py.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.document import Document
from app.models.policy import (
    EMBEDDING_DIMENSION,
    Policy,
    PolicyChunk,
    PolicyClassification,
    PolicyVersion,
    PolicyVersionStatus,
)
from services import assistant
from services.policy_retrieval import EmbeddingServiceError, search_policies_by_keywords

ZERO_VECTOR = [0.0] * EMBEDDING_DIMENSION


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


def add_policy(
    db,
    *,
    org="org-a",
    name="Leave Policy",
    text="Employees may carry over 5 leave days.",
    classification=PolicyClassification.INTERNAL,
    document_type=None,
    is_active=True,
    status=PolicyVersionStatus.ACTIVE,
    with_source=True,
    source_org=None,
):
    policy = Policy(
        organization_id=org, name=name, classification=classification,
        document_type=document_type, is_active=is_active,
    )
    db.add(policy)
    db.flush()
    source_id = None
    if with_source:
        source = Document(
            organization_id=source_org or org, uploaded_by="admin", filename=f"{name}.pdf",
            file_type="application/pdf", file_size=1, storage_path=f"{name}.pdf",
        )
        db.add(source)
        db.flush()
        source_id = source.id
    version = PolicyVersion(policy_id=policy.id, source_document_id=source_id, version="v1", status=status)
    db.add(version)
    db.flush()
    db.add(PolicyChunk(
        policy_version_id=version.id, content=text, embedding=ZERO_VECTOR, chunk_index=0, chunk_metadata={},
    ))
    db.flush()
    return policy


def search(db, keywords=("leave",), *, org="org-a", role="SUBMITTER", document_type=None):
    rows = search_policies_by_keywords(db, org, role, list(keywords), document_type, limit=10)
    return [row[0].name for row in rows]


def test_other_organizations_policies_are_never_returned(db):
    add_policy(db, org="org-b", name="Beta Leave")
    assert search(db) == []


@pytest.mark.parametrize(
    ("classification", "allowed_roles"),
    [
        (PolicyClassification.PUBLIC, {"SUBMITTER", "REVIEWER", "ORG_ADMIN"}),
        (PolicyClassification.INTERNAL, {"SUBMITTER", "REVIEWER", "ORG_ADMIN"}),
        (PolicyClassification.REVIEWER_ONLY, {"REVIEWER", "ORG_ADMIN"}),
        (PolicyClassification.CONFIDENTIAL, {"ORG_ADMIN"}),
        (PolicyClassification.RESTRICTED, {"ORG_ADMIN"}),
    ],
)
def test_keyword_fallback_respects_policy_classification(db, classification, allowed_roles):
    add_policy(db, classification=classification)
    for role in ("SUBMITTER", "REVIEWER", "ORG_ADMIN"):
        assert bool(search(db, role=role)) == (role in allowed_roles), f"{classification.value} / {role}"


def test_inactive_policy_and_non_active_versions_are_hidden(db):
    add_policy(db, name="Inactive", is_active=False)
    add_policy(db, name="Archived", status=PolicyVersionStatus.ARCHIVED)
    add_policy(db, name="Failed", status=PolicyVersionStatus.FAILED)
    add_policy(db, name="Processing", status=PolicyVersionStatus.PROCESSING)
    assert search(db) == []


def test_document_type_filter_applies_to_keyword_fallback(db):
    add_policy(db, name="Invoice Rules", document_type="invoice")
    add_policy(db, name="Resume Rules", document_type="resume")
    assert search(db, document_type="invoice") == ["Invoice Rules"]


def test_policy_without_a_source_document_is_still_searchable(db):
    add_policy(db, with_source=False)
    assert search(db) == ["Leave Policy"]


def test_policy_whose_source_document_belongs_to_another_org_is_hidden(db):
    add_policy(db, source_org="org-b")
    assert search(db) == []


@pytest.mark.parametrize("wildcard", ["%", "_", "le_ve"])
def test_like_wildcards_in_the_question_are_matched_literally(db, wildcard):
    add_policy(db, text="Employees may carry over 5 days.", name="Plain")
    assert search(db, keywords=(wildcard,)) == []


def test_chunks_matching_more_keywords_rank_first(db):
    add_policy(db, name="One", text="leave only")
    add_policy(db, name="Two", text="leave and carry over rules")
    assert search(db, keywords=("leave", "carry"))[0] == "Two"


def test_no_keywords_returns_nothing(db):
    add_policy(db)
    assert search(db, keywords=()) == []


# --- assistant: when does it fall back to keyword search? -----------------------------------
def test_assistant_uses_keyword_search_only_when_embeddings_are_unavailable(db, monkeypatch):
    add_policy(db, classification=PolicyClassification.RESTRICTED)
    add_policy(db, name="Public Leave", classification=PolicyClassification.PUBLIC)

    def embeddings_down(_query):
        raise EmbeddingServiceError("down")

    monkeypatch.setattr(assistant, "create_query_embedding", embeddings_down)
    rows = assistant._find_policy_rows(db, "what is the leave policy", "org-a", "SUBMITTER", None)
    assert [row[0].name for row in rows] == ["Public Leave"]  # RESTRICTED policy is not leaked


def test_assistant_does_not_hide_unexpected_errors_behind_the_fallback(db, monkeypatch):
    def broken(_query):
        raise RuntimeError("bug")

    monkeypatch.setattr(assistant, "create_query_embedding", broken)
    with pytest.raises(RuntimeError):
        assistant._find_policy_rows(db, "leave policy", "org-a", "SUBMITTER", None)
