"""Vector retrieval with document types and exact figures, on real PostgreSQL + pgvector (RAG Phase 3).

Skipped unless QA10_TEST_DATABASE_URL points at a database with the vector extension; every
test runs in a throwaway schema inside a transaction that is rolled back.
"""
import pytest

from app.models.policy import PolicyVersionStatus
from services import policy_retrieval
from tests.test_qa10_policy_retrieval import add_policy_version, finance_policy, policy_db, search, vector  # noqa: F401

ACTIVE = PolicyVersionStatus.ACTIVE


def chunk_texts(result) -> list[str]:
    return [row[2].content for row in result.rows]


def test_a_document_type_matches_in_any_spelling_and_policies_for_every_type_still_apply(policy_db):  # noqa: F811
    db = policy_db
    add_policy_version(db, finance_policy(document_type="invoice"), "v1", ACTIVE, vector(1.0, 0.0), "Invoices need a PO.")
    add_policy_version(db, finance_policy(document_type=None), "v2", ACTIVE, vector(1.0, 0.0), "Everything needs a receipt.")
    db.expire_all()

    for spelling in ("financial", "INVOICES", "Expense Claim"):
        found = chunk_texts(search(db, domain=None, document_type=spelling))
        assert sorted(found) == ["Everything needs a receipt.", "Invoices need a PO."], spelling

    assert chunk_texts(search(db, domain=None, document_type="transcript")) == ["Everything needs a receipt."]


def test_chunks_containing_the_figures_of_the_question_rank_first(policy_db):  # noqa: F811
    db = policy_db
    closest = add_policy_version(db, finance_policy(), "v1", ACTIVE, vector(1.0, 0.0), "General approval rules.")
    figure = add_policy_version(
        db, finance_policy(), "v2", ACTIVE, vector(0.95, 0.3122), "2.3 Claims above $500 need approval."
    )
    db.expire_all()

    ranked = policy_retrieval.retrieve_policy_evidence(
        db, "org-a", "ORG_ADMIN", vector(1.0, 0.0), None, "invoice", None, 1, query_text="What does clause 2.3 say?"
    )
    assert [row[2].id for row in ranked.rows] == [figure]

    plain = policy_retrieval.retrieve_policy_evidence(
        db, "org-a", "ORG_ADMIN", vector(1.0, 0.0), None, "invoice", None, 1, query_text="What are the approval rules?"
    )
    assert [row[2].id for row in plain.rows] == [closest]


def test_a_figure_cannot_pull_in_a_chunk_below_the_relevance_floor(policy_db):  # noqa: F811
    db = policy_db
    add_policy_version(
        db, finance_policy(), "v1", ACTIVE, vector(0.0, 1.0), "2.3 Unrelated clause that happens to contain the number."
    )
    db.expire_all()

    result = policy_retrieval.retrieve_policy_evidence(
        db, "org-a", "ORG_ADMIN", vector(1.0, 0.0), None, "invoice", None, 5, query_text="clause 2.3"
    )
    assert result.outcome == "low_relevance" and result.rows == []


def test_identical_clauses_in_two_policies_are_returned_once(policy_db):  # noqa: F811
    db = policy_db
    for version, vec in (("v1", vector(1.0, 0.0)), ("v2", vector(0.9, 0.436))):
        add_policy_version(db, finance_policy(), version, ACTIVE, vec, "Keep every receipt for seven years.")
    db.expire_all()

    assert chunk_texts(search(db, domain=None)) == ["Keep every receipt for seven years."]
