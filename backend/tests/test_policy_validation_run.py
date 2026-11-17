"""Policy validation: what is trusted, what needs review (RAG Phase 4).

The language model, embeddings and clause search are replaced by fakes, so these tests pin
down the decisions made in code. The real stack is exercised by tests/rag_eval/e2e_check.py.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.document import Document
from app.models.extraction import Extraction
from services import policy_validation
from services.embeddings import EmbeddingServiceError
from services.llm import LLMServiceError
from services.policy_retrieval import RetrievalResult

CLAUSE_A = "Expenses: 2.3 Any single expense claim with a total above $500 requires prior written approval."
CLAUSE_B = "Invoices: 4.2 Standard payment terms are Net 30 days from the invoice date."
IDENTITY = {"sub": "reviewer-1", "role": "REVIEWER", "organization_id": "org-a", "active": True}


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


def make_document(db, classification="financial", fields=None, org="org-a"):
    document = Document(
        organization_id=org, uploaded_by="u1", filename="invoice.pdf", file_type="application/pdf",
        file_size=1, storage_path="invoice.pdf", classification=classification,
    )
    db.add(document)
    db.flush()
    for name, (value, confidence) in (fields if fields is not None else {"total_amount": ("740.00", 0.95)}).items():
        db.add(Extraction(document_id=document.id, field_name=name, value=value, confidence=confidence))
    db.commit()
    return document


def clause(chunk_id, text, policy="Expense Policy"):
    return (
        SimpleNamespace(id=f"p-{policy}", name=policy, domain="finance", document_type="financial"),
        SimpleNamespace(id=f"v-{policy}", version="v1", source_document_id=None),
        SimpleNamespace(id=chunk_id, chunk_index=0, page_number=None, section="Expenses", content=text),
        0.8,
        None,
    )


def finding(status="PASS", chunk="c1", quote="total above $500 requires prior written approval", **extra):
    return {
        "status": status, "requirement": extra.pop("requirement", "Approval above $500"),
        "explanation": "Judged against the clause.", "field_name": "total_amount", "document_value": "740.00",
        "confidence": 0.9, "source_chunk_ids": [chunk], "source_quotes": [{"source_chunk_id": chunk, "quote": quote}],
        **extra,
    }


class Fakes:
    """Controls what the embedding, clause search and model return for one test."""

    def __init__(self):
        self.rows = [clause("c1", CLAUSE_A)]
        self.outcome = "full_scope"
        self.incomplete = []
        self.draft = {"summary": "Checked.", "findings": [finding()], "irrelevant_chunk_ids": []}
        self.embedding_error = None
        self.llm_error = None
        self.calls = {"embed": 0, "search": 0, "llm": 0}


@pytest.fixture
def fakes(monkeypatch):
    fake = Fakes()

    def embed(queries):
        fake.calls["embed"] += 1
        if fake.embedding_error:
            raise fake.embedding_error
        return [[0.0] for _ in queries]

    def search(*_args, **_kwargs):
        fake.calls["search"] += 1
        return RetrievalResult(fake.outcome, fake.rows, fake.incomplete)

    def judge(_system, _user):
        fake.calls["llm"] += 1
        if fake.llm_error:
            raise fake.llm_error
        return fake.draft

    monkeypatch.setattr(policy_validation, "create_query_embeddings", embed)
    monkeypatch.setattr(policy_validation, "retrieve_policy_validation_evidence", search)
    monkeypatch.setattr(policy_validation, "chat_json", judge)
    return fake


def run(db, document):
    return policy_validation.run_policy_validation(db, document, IDENTITY)


def statuses(result):
    return [item.status for item in result.findings]


def test_a_verified_pass_is_reported_with_its_quoted_source(db, fakes):
    result = run(db, make_document(db))

    assert result.status == "PASS" and result.retrieval_outcome == "full_scope"
    (item,) = result.findings
    assert item.status == "PASS"
    reference = item.source_references[0]
    assert reference["supporting_quote"] == "total above $500 requires prior written approval"
    assert reference["policy_domain"] == "finance" and reference["policy_version"] == "v1"
    assert result.policy_versions[0]["version"] == "v1"


def test_a_verified_fail_on_a_confident_field_is_a_fail(db, fakes):
    fakes.draft["findings"] = [finding("FAIL", document_value="$740")]  # same number, written differently
    assert run(db, make_document(db)).status == "FAIL"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"document_value": "9999"}, "does not match the persisted extraction"),
        ({"document_value": None}, "must identify the persisted value"),
        ({"field_name": "invented_field"}, "not present in the persisted extraction"),
        ({"field_name": None}, "tied to a persisted document field"),
        ({"confidence": 0.3}, "confidence below the configured review threshold"),
    ],
)
def test_a_fail_that_cannot_be_tied_to_the_stored_data_is_downgraded_to_review(db, fakes, change, reason):
    fakes.draft["findings"] = [finding("FAIL", **change)]
    result = run(db, make_document(db))
    assert result.status == "NEEDS_HUMAN_REVIEW"
    assert reason in result.findings[0].explanation and result.findings[0].status == "NEEDS_HUMAN_REVIEW"


def test_a_fail_on_a_low_confidence_extraction_is_not_a_confirmed_violation(db, fakes):
    fakes.draft["findings"] = [finding("FAIL")]
    result = run(db, make_document(db, fields={"total_amount": ("740.00", 0.55)}))
    assert result.status == "NEEDS_HUMAN_REVIEW"
    assert any("not a confirmed violation" in item.explanation for item in result.findings)
    assert "below the configured confidence threshold" in result.summary


@pytest.mark.parametrize(
    "bad_citation",
    [
        {"source_quotes": [{"source_chunk_id": "c1", "quote": "a sentence that is not in the clause at all"}]},
        {"source_chunk_ids": ["made-up"], "source_quotes": [{"source_chunk_id": "made-up", "quote": "total above $500 requires"}]},
        {"source_quotes": []},
        {"source_chunk_ids": []},
    ],
    ids=["fabricated-quote", "invented-chunk", "no-quote", "no-citation"],
)
def test_a_finding_without_a_verifiable_citation_is_never_trusted(db, fakes, bad_citation):
    fakes.draft["findings"] = [{**finding("PASS"), **bad_citation}]
    result = run(db, make_document(db))
    assert result.status == "NEEDS_HUMAN_REVIEW"
    assert "lacked a verifiable quoted excerpt" in result.findings[0].explanation


def test_quotes_match_ignoring_case_and_spacing(db, fakes):
    fakes.draft["findings"] = [finding(quote="TOTAL  above $500\nrequires prior written approval")]
    assert run(db, make_document(db)).status == "PASS"


def test_clauses_the_model_neither_used_nor_ruled_out_block_a_pass(db, fakes):
    fakes.rows = [clause("c1", CLAUSE_A), clause("c2", CLAUSE_B, policy="Invoice Policy")]
    result = run(db, make_document(db))
    assert result.status == "NEEDS_HUMAN_REVIEW"
    coverage = [item for item in result.findings if item.requirement == "Policy corpus coverage"]
    assert len(coverage) == 1 and "1 policy clause(s)" in coverage[0].explanation


def test_clauses_ruled_out_as_irrelevant_do_not_block_a_pass_and_are_reported(db, fakes):
    fakes.rows = [clause("c1", CLAUSE_A), clause("c2", CLAUSE_B, policy="Invoice Policy")]
    fakes.draft["irrelevant_chunk_ids"] = ["c2", "not-a-real-chunk"]
    result = run(db, make_document(db))
    assert result.status == "PASS"
    assert "1 policy clause(s) were reviewed and judged not to apply" in result.summary


def test_a_model_that_finds_nothing_to_check_cannot_imply_a_pass(db, fakes):
    fakes.draft = {"summary": "Nothing.", "findings": [], "irrelevant_chunk_ids": ["c1"]}
    result = run(db, make_document(db))
    assert result.status == "NEEDS_HUMAN_REVIEW" and result.findings[0].requirement == "Policy check coverage"


def test_the_same_requirement_judged_pass_and_fail_needs_review(db, fakes):
    fakes.draft["findings"] = [finding("PASS"), finding("FAIL")]
    result = run(db, make_document(db))
    assert result.status == "NEEDS_HUMAN_REVIEW"
    assert statuses(result) == ["NEEDS_HUMAN_REVIEW", "NEEDS_HUMAN_REVIEW"]


def test_a_requirement_about_a_field_that_was_not_extracted_is_missing_information(db, fakes):
    fakes.draft["findings"] = [finding("FAIL", field_name="invoice_number", document_value=None)]
    result = run(db, make_document(db, fields={"total_amount": ("740.00", 0.95)}))
    assert result.status == "NEEDS_HUMAN_REVIEW" and statuses(result)[0] == "MISSING_INFORMATION"


@pytest.mark.parametrize(
    ("error", "attr"),
    [(LLMServiceError("down"), "llm_error"), (None, "draft")],
    ids=["model-unavailable", "malformed-answer"],
)
def test_an_unusable_model_answer_gives_a_review_result_not_an_error(db, fakes, error, attr):
    if error:
        fakes.llm_error = error
    else:
        fakes.draft = {"findings": "not a list"}
    result = run(db, make_document(db))
    assert result.status == "NEEDS_HUMAN_REVIEW"
    assert result.findings[0].requirement == "Policy evidence evaluation"
    assert result.findings[0].source_references  # the clauses that were found are still shown


def test_an_applicable_policy_that_cannot_be_searched_is_reported_but_does_not_hide_other_results(db, fakes):
    fakes.incomplete = [{"policy_id": "p-x", "policy_name": "Travel Policy", "version": "v3"}]
    result = run(db, make_document(db))
    assert result.status == "NEEDS_HUMAN_REVIEW"
    assert "PASS" in statuses(result)  # the policy that could be checked still has its finding
    unchecked = [item for item in result.findings if item.requirement.startswith("Policy not checked")]
    assert unchecked[0].requirement == "Policy not checked: Travel Policy"
    last = result.policy_versions[-1]
    assert (last["policy_name"], last["version"], last["index_status"]) == ("Travel Policy", "v3", "NOT_SEARCHABLE")


@pytest.mark.parametrize(
    ("setup", "outcome", "searches"),
    [
        ({"fields": {}}, "no_extractions", 0),
        ({"embedding_error": EmbeddingServiceError("down")}, "unavailable", 0),
        ({"outcome": "no_applicable_policies", "rows": []}, "no_applicable_policies", 1),
        ({"outcome": "unindexed_policy_evidence", "rows": [], "incomplete": [{"policy_id": "p", "policy_name": "P", "version": "v1"}]}, "unindexed_policy_evidence", 1),
    ],
    ids=["no-fields", "search-service-down", "no-policy-applies", "nothing-indexed"],
)
def test_when_there_is_nothing_to_check_against_the_result_says_so_and_asks_for_review(db, fakes, setup, outcome, searches):
    fields = setup.pop("fields", None)
    for name, value in setup.items():
        setattr(fakes, name, value)
    result = run(db, make_document(db, fields=fields))
    assert result.status == "NEEDS_HUMAN_REVIEW" and result.retrieval_outcome == outcome
    assert fakes.calls["search"] == searches and fakes.calls["llm"] == 0
    assert "No violation was inferred" in " ".join(item.explanation for item in result.findings)


def test_an_unclassified_document_is_checked_but_always_needs_review(db, fakes):
    result = run(db, make_document(db, classification=None))
    assert result.status == "NEEDS_HUMAN_REVIEW"
    assert "has no classification" in result.summary and "PASS" in statuses(result)


def test_low_confidence_extractions_force_review_and_are_listed(db, fakes):
    result = run(db, make_document(db, fields={"total_amount": ("740.00", 0.95), "invoice_number": ("INV-1", 0.4)}))
    assert result.status == "NEEDS_HUMAN_REVIEW"
    low = [item for item in result.findings if item.field_name == "invoice_number"]
    assert low and "0.40" in low[0].explanation and "1 extracted field(s) are below" in result.summary


def test_a_partial_subset_says_so(db, fakes):
    fakes.outcome = "relevant_subset"
    result = run(db, make_document(db))
    assert result.retrieval_outcome == "relevant_subset"
    assert "most relevant to the document" in result.summary


def test_one_search_is_made_for_the_document_and_one_for_each_field(db, fakes, monkeypatch):
    seen = []
    monkeypatch.setattr(policy_validation, "create_query_embeddings", lambda queries: seen.extend(queries) or [[0.0]] * len(queries))
    run(db, make_document(db, fields={"total_amount": ("740.00", 0.9), "invoice_number": ("INV-1", 0.9), "blank": (" ", 0.9)}))
    assert seen[0].startswith("financial - ") and "total_amount: 740.00" in seen[0]
    assert seen[1:] == ["invoice number: INV-1", "total amount: 740.00"]  # blank value skipped, ordered by name


def test_another_organizations_document_is_refused_before_anything_runs(db, fakes):
    document = make_document(db, org="org-b")
    with pytest.raises(HTTPException) as error:
        run(db, document)
    assert error.value.status_code == 403 and fakes.calls == {"embed": 0, "search": 0, "llm": 0}


@pytest.mark.parametrize(
    ("stated", "stored", "same"),
    [("740", "740.00", True), ("$740.00", "740", True), ("1,000", "1000.0", True), ("740", "741", False), ("Acme", " acme ", True), ("Acme", "Beta", False)],
)
def test_values_are_compared_as_text_or_as_numbers(stated, stored, same):
    assert policy_validation._same_value(stated, stored) is same
