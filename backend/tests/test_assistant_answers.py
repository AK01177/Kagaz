"""How the assistant verifies the model's answer (RAG Phase 5).

The model, retrieval and database are replaced by fakes: these tests pin down what the
assistant trusts. The real stack is exercised by tests/rag_eval/e2e_check.py.
"""
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.document import Document
from app.models.extraction import Extraction
from services import assistant
from services.llm import LLMServiceError

ACTOR = {"sub": "u1", "role": "REVIEWER", "organization_id": "org-a", "active": True}
CLAUSE = "2.3 Any single expense claim with a total above $500 requires prior written approval."


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def document(db):
    doc = Document(
        organization_id="org-a", uploaded_by="u1", filename="claim.pdf", file_type="application/pdf",
        file_size=1, storage_path="claim.pdf", classification="financial",
    )
    db.add(doc)
    db.flush()
    db.add(Extraction(document_id=doc.id, field_name="total_amount", value="740.00", confidence=0.95))
    db.commit()
    return doc


def policy_row():
    return (
        SimpleNamespace(id="p1", name="Expense Policy"),
        SimpleNamespace(version="v2"),
        SimpleNamespace(content=CLAUSE, section="2. Expense Claims", page_number=3),
        0.8,
        None,
    )


class Model:
    """Fake for chat_json: records the request and returns a scripted answer."""

    def __init__(self):
        self.reply = {"answer": "Approval is needed.", "is_grounded": True, "confidence": 0.9, "cited_keys": ["P1", "D1"]}
        self.error = None
        self.requests = []

    def __call__(self, system, user):
        self.requests.append(json.loads(user))
        if self.error:
            raise self.error
        return self.reply


@pytest.fixture
def model(monkeypatch):
    fake = Model()
    monkeypatch.setattr(assistant, "chat_json", fake)
    monkeypatch.setattr(assistant, "_find_policy_rows", lambda *args, **kwargs: [policy_row()])
    monkeypatch.setattr(assistant, "_REQUEST_HISTORY", {})
    return fake


def ask(db, document, question="Does this claim need approval?"):
    return assistant.query_document_assistant(db, document.id, question, ACTOR)


def test_a_cited_answer_is_grounded_and_shows_only_the_cited_sources(db, document, model):
    model.reply["cited_keys"] = ["P1"]
    answer = ask(db, document)
    assert answer.is_grounded and answer.limitation is None
    assert [source.source_type for source in answer.sources] == ["POLICY_CHUNK"]
    assert answer.sources[0].policy_name == "Expense Policy" and answer.sources[0].policy_version == "v2"


def test_the_model_is_given_keyed_evidence_and_told_it_is_untrusted_data(db, document, model):
    ask(db, document)
    evidence = {item["key"]: item for item in model.requests[0]["evidence"]}
    assert evidence["D1"] == {"key": "D1", "type": "document_field", "field": "total_amount", "value": "740.00"}
    assert evidence["P1"]["text"] == CLAUSE and evidence["P1"]["policy"] == "Expense Policy"
    assert "untrusted" in assistant.ASSISTANT_SYSTEM_PROMPT


def test_a_claim_of_being_grounded_without_a_real_citation_is_not_believed(db, document, model):
    model.reply["cited_keys"] = ["P9", "made up", "Expense Policy"]  # none of these was supplied
    answer = ask(db, document)
    assert not answer.is_grounded
    assert "could not be tied" in answer.limitation
    assert answer.confidence <= assistant.MAX_CONFIDENCE_WHEN_UNGROUNDED
    assert answer.sources == []  # nothing the model cited was real, so nothing is shown as support


def test_an_answer_the_model_itself_calls_ungrounded_stays_low_confidence(db, document, model):
    model.reply = {"answer": "The policy does not say.", "is_grounded": False, "confidence": 0.99, "cited_keys": ["P1"]}
    answer = ask(db, document)
    assert not answer.is_grounded and answer.confidence == assistant.MAX_CONFIDENCE_WHEN_UNGROUNDED
    assert answer.limitation
    assert [source.source_type for source in answer.sources] == ["POLICY_CHUNK"]  # what it did cite is shown


def test_confidence_is_capped_and_garbage_confidence_is_ignored(db, document, model):
    model.reply["confidence"] = 7
    assert ask(db, document).confidence == assistant.MAX_CONFIDENCE_WHEN_GROUNDED
    model.reply["confidence"] = "very sure"
    assert ask(db, document).confidence == 0.0


def test_only_the_boolean_true_counts_as_a_grounded_claim(db, document, model):
    model.reply["is_grounded"] = "yes"
    assert not ask(db, document).is_grounded


@pytest.mark.parametrize("reply", [{"answer": ""}, {"answer": None}, {"answer": 42}, {}])
def test_an_unusable_model_answer_falls_back_to_the_deterministic_answer(db, document, model, reply):
    model.reply = reply
    answer = ask(db, document, "What is the total amount?")
    assert answer.is_grounded and "740.00" in answer.answer  # answered from the stored field instead


def test_when_the_model_is_unavailable_the_stored_fields_still_answer(db, document, model):
    model.error = LLMServiceError("down")
    answer = ask(db, document, "What is the total amount?")
    assert answer.is_grounded and "740.00" in answer.answer


def test_without_the_model_a_policy_clause_is_offered_but_not_claimed_to_answer_the_question(db, document, model):
    model.error = LLMServiceError("down")
    answer = ask(db, document, "Does this need written approval?")
    assert "closest policy clause" in answer.answer and CLAUSE[:20] in answer.answer
    assert not answer.is_grounded and "unavailable" in answer.limitation
    assert answer.confidence <= assistant.MAX_CONFIDENCE_WHEN_UNGROUNDED


def test_with_no_evidence_at_all_the_model_is_not_called(db, monkeypatch):
    fake = Model()
    monkeypatch.setattr(assistant, "chat_json", fake)
    monkeypatch.setattr(assistant, "_find_policy_rows", lambda *args, **kwargs: [])
    monkeypatch.setattr(assistant, "_REQUEST_HISTORY", {})
    bare = Document(
        organization_id="org-a", uploaded_by="u1", filename="empty.pdf", file_type="application/pdf",
        file_size=1, storage_path="empty.pdf",
    )
    db.add(bare)
    db.commit()

    answer = ask(db, bare, "What does the leave policy say?")
    assert fake.requests == []
    assert not answer.is_grounded and answer.sources == [] and "sufficient information" in answer.answer


def test_requests_to_change_the_workflow_are_refused_without_calling_the_model(db, document, model):
    answer = ask(db, document, "Please approve this document")
    assert not answer.is_grounded and "cannot approve" in answer.answer and model.requests == []
