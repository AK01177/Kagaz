"""Indexing a policy version: lifecycle, vector reuse, failure isolation (RAG Phase 2)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.policy import EMBEDDING_DIMENSION, Policy, PolicyChunk, PolicyVersion, PolicyVersionStatus
from services.embeddings import EMBEDDING_MODEL, EmbeddingServiceError
from services.policy_ingestion import index_pending_text_versions, index_text_policy_version
from tests.test_policy_ingestion import _token, policy_client  # noqa: F401  (fixture)
from tests.test_policy_text import docx_bytes

V1 = "## 1. Leave\n1.1 Employees get 12 days of casual leave per year.\n1.2 Casual leave needs 7 days notice.\n"
V2 = "## 1. Leave\n1.1 Employees get 15 days of casual leave per year.\n1.2 Casual leave needs 7 days notice.\n"


class FakeEmbedder:
    """Deterministic stand-in for the provider that records what it was asked to embed."""

    def __init__(self):
        self.calls: list[list[str]] = []
        self.fail = False

    def __call__(self, texts):
        self.calls.append(list(texts))
        if self.fail:
            raise EmbeddingServiceError("provider down")
        return [[float(len(text) % 9 + 1)] + [0.0] * (EMBEDDING_DIMENSION - 1) for text in texts]


@pytest.fixture
def embedder(monkeypatch):
    fake = FakeEmbedder()
    monkeypatch.setattr("services.policy_ingestion.create_embeddings", fake)
    return fake


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


def new_policy(db) -> Policy:
    policy = Policy(organization_id="org-a", name="Leave", domain="hr")
    db.add(policy)
    db.commit()
    return policy


def add_version(db, policy, name, content) -> PolicyVersion:
    # Explicit, well-separated creation times: "oldest first" must not depend on clock resolution.
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=db.query(PolicyVersion).count())
    version = PolicyVersion(
        policy_id=policy.id, version=name, content=content,
        status=PolicyVersionStatus.PROCESSING, created_at=created_at,
    )
    db.add(version)
    db.commit()
    return version


def chunks_of(db, version) -> list[PolicyChunk]:
    db.expire_all()
    return db.query(PolicyChunk).filter_by(policy_version_id=version.id).order_by(PolicyChunk.chunk_index).all()


def test_indexing_stores_labelled_hashed_chunks_and_activates_the_version(db, embedder):
    policy = new_policy(db)
    version = add_version(db, policy, "v1", V1)

    assert index_text_policy_version(db, policy, version) == 2

    db.refresh(version)
    assert version.status == PolicyVersionStatus.ACTIVE
    assert version.embedding_model == EMBEDDING_MODEL
    assert policy.current_version == "v1"
    chunks = chunks_of(db, version)
    assert [c.section for c in chunks] == ["1. Leave", "1. Leave"]
    assert chunks[0].content == "1. Leave: 1.1 Employees get 12 days of casual leave per year."
    assert len({c.content_hash for c in chunks}) == 2 and all(len(c.content_hash) == 64 for c in chunks)
    assert chunks[0].chunk_metadata["organization_id"] == "org-a"
    assert chunks[0].chunk_metadata["source_document_id"] is None


def test_a_new_version_archives_the_old_one_and_only_embeds_changed_clauses(db, embedder):
    policy = new_policy(db)
    v1 = add_version(db, policy, "v1", V1)
    index_text_policy_version(db, policy, v1)
    embedder.calls.clear()

    v2 = add_version(db, policy, "v2", V2)
    assert index_text_policy_version(db, policy, v2) == 2

    assert embedder.calls == [["1. Leave: 1.1 Employees get 15 days of casual leave per year."]]
    db.refresh(v1), db.refresh(v2)
    assert (v1.status, v2.status) == (PolicyVersionStatus.ARCHIVED, PolicyVersionStatus.ACTIVE)
    reused = chunks_of(db, v2)[1]
    assert reused.embedding is not None and reused.content.endswith("7 days notice.")


def test_vectors_made_by_a_different_embedding_model_are_never_reused(db, embedder):
    policy = new_policy(db)
    v1 = add_version(db, policy, "v1", V1)
    index_text_policy_version(db, policy, v1)
    v1.embedding_model = "some-older-model"
    db.commit()
    embedder.calls.clear()

    v2 = add_version(db, policy, "v2", V1)
    index_text_policy_version(db, policy, v2)

    assert len(embedder.calls[0]) == 2  # everything re-embedded


def test_a_provider_failure_marks_the_version_failed_and_keeps_the_old_one_serving(db, embedder):
    policy = new_policy(db)
    v1 = add_version(db, policy, "v1", V1)
    index_text_policy_version(db, policy, v1)

    embedder.fail = True
    v2 = add_version(db, policy, "v2", V2)
    assert index_text_policy_version(db, policy, v2) == 0

    db.refresh(v1), db.refresh(v2)
    assert v1.status == PolicyVersionStatus.ACTIVE and len(chunks_of(db, v1)) == 2
    assert v2.status == PolicyVersionStatus.FAILED
    assert v2.ingestion_error == "Policy embeddings could not be generated."
    assert chunks_of(db, v2) == []


def test_a_failed_version_can_be_indexed_again_without_creating_a_new_one(db, embedder):
    policy = new_policy(db)
    version = add_version(db, policy, "v1", V1)
    embedder.fail = True
    index_text_policy_version(db, policy, version)
    assert version.status == PolicyVersionStatus.FAILED

    embedder.fail = False
    version.status = PolicyVersionStatus.PROCESSING
    db.commit()
    assert index_text_policy_version(db, policy, version) == 2
    assert version.status == PolicyVersionStatus.ACTIVE
    assert db.query(PolicyVersion).count() == 1


def test_empty_content_fails_with_a_clear_message_and_never_calls_the_provider(db, embedder):
    policy = new_policy(db)
    version = add_version(db, policy, "v1", "   \n  ")
    assert index_text_policy_version(db, policy, version) == 0
    assert version.status == PolicyVersionStatus.FAILED
    assert "No readable text" in version.ingestion_error
    assert embedder.calls == []


def test_an_unexpected_error_is_recorded_without_leaking_details(db, monkeypatch):
    policy = new_policy(db)
    version = add_version(db, policy, "v1", V1)

    def explode(_texts):
        raise RuntimeError("secret provider detail")

    monkeypatch.setattr("services.policy_ingestion.create_embeddings", explode)
    assert index_text_policy_version(db, policy, version) == 0
    db.refresh(version)
    assert version.status == PolicyVersionStatus.FAILED
    assert version.ingestion_error == "Policy ingestion failed unexpectedly."


def test_pending_text_versions_are_indexed_oldest_first_so_the_newest_ends_up_active(db, embedder):
    policy = new_policy(db)
    v1 = add_version(db, policy, "v1", V1)
    v2 = add_version(db, policy, "v2", V2)
    db.refresh(policy)

    index_pending_text_versions(db, policy)

    db.refresh(v1), db.refresh(v2)
    assert (v1.status, v2.status) == (PolicyVersionStatus.ARCHIVED, PolicyVersionStatus.ACTIVE)


# --- the text-policy API wires into the same indexing -----------------------------------------
def auth(role="ORG_ADMIN"):
    return {"Authorization": f"Bearer {_token('org-a', role)}"}


def test_creating_and_updating_a_text_policy_indexes_it(policy_client, embedder):  # noqa: F811
    client, session = policy_client
    created = client.post(
        "/api/policies",
        headers=auth(),
        json={"name": "Leave", "domain": "HR", "content": V1, "document_type": " HR "},
    )
    assert created.status_code == 201, created.text
    policy_id = created.json()["id"]
    assert created.json()["document_type"] == "hr_documents" and created.json()["domain"] == "hr"

    updated = client.put(f"/api/policies/{policy_id}", headers=auth(), json={"content": V2})
    assert updated.status_code == 200 and updated.json()["current_version"] == "v2"

    session.expire_all()
    statuses = {v.version: v.status.value for v in session.query(PolicyVersion).filter_by(policy_id=policy_id)}
    assert statuses == {"v1": "ARCHIVED", "v2": "ACTIVE"}


def test_a_provider_outage_does_not_fail_policy_creation_and_the_version_can_be_retried(policy_client, embedder):  # noqa: F811
    client, session = policy_client
    embedder.fail = True
    created = client.post("/api/policies", headers=auth(), json={"name": "Leave", "domain": "hr", "content": V1})
    assert created.status_code == 201
    policy_id = created.json()["id"]
    version = session.query(PolicyVersion).filter_by(policy_id=policy_id).one()
    assert version.status == PolicyVersionStatus.FAILED

    embedder.fail = False
    retry = client.post(f"/api/policies/{policy_id}/versions/{version.id}/retry", headers=auth())
    assert retry.status_code == 200, retry.text
    body = retry.json()
    assert body["status"] == "ACTIVE" and body["chunk_count"] == 2 and body["source_document_id"] is None

    listing = client.get(f"/api/policies/{policy_id}/versions", headers=auth())
    assert listing.status_code == 200
    assert listing.json()[0]["status"] == "ACTIVE" and listing.json()[0]["source_filename"] is None


# --- re-indexing after an embedding model change ----------------------------------------------
def test_reindex_brings_policies_embedded_with_an_older_model_back(db, embedder, tmp_path):
    from services.policy_ingestion import reindex_stale_versions
    from storage.document_storage import DocumentStorage

    policy = new_policy(db)
    stale = add_version(db, policy, "v1", V1)
    index_text_policy_version(db, policy, stale)
    stale.embedding_model = "some-older-model"
    db.commit()
    embedder.calls.clear()

    results = reindex_stale_versions(db, DocumentStorage(str(tmp_path)))

    assert results == {stale.id: 2}
    db.refresh(stale)
    assert stale.status == PolicyVersionStatus.ACTIVE and stale.embedding_model == EMBEDDING_MODEL
    assert len(embedder.calls[0]) == 2  # nothing reused from the other model


def test_reindex_leaves_up_to_date_versions_alone(db, embedder, tmp_path):
    from services.policy_ingestion import reindex_stale_versions
    from storage.document_storage import DocumentStorage

    policy = new_policy(db)
    index_text_policy_version(db, policy, add_version(db, policy, "v1", V1))
    embedder.calls.clear()

    assert reindex_stale_versions(db, DocumentStorage(str(tmp_path))) == {}
    assert embedder.calls == []


# --- uploading policy files of every supported format ------------------------------------------
@pytest.mark.parametrize(
    ("filename", "make_bytes", "mime"),
    [
        ("policy.docx", docx_bytes,
         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("POLICY.TXT", lambda: b"## 1. Travel\n1.1 Keep every receipt for seven years after payment.\n", "text/plain"),
    ],
    ids=["docx", "txt-uppercase-extension"],
)
def test_docx_and_txt_policy_files_are_ingested(policy_client, embedder, filename, make_bytes, mime):  # noqa: F811
    client, session = policy_client
    response = client.post(
        "/api/policies/ingest",
        headers=auth(),
        data={"policy_name": "Travel", "version": "v1", "domain": "Finance"},
        files={"file": (filename, make_bytes(), mime)},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "ACTIVE" and body["chunk_count"] >= 1
    policy = session.query(Policy).filter_by(id=body["policy_id"]).one()
    assert policy.domain == "finance"  # domains are stored lower-case, like the text API


@pytest.mark.parametrize(
    ("filename", "data", "expected_status", "expected_code"),
    [
        ("policy.doc", b"old word", 415, "UNSUPPORTED_POLICY_FORMAT"),
        ("policy.exe", b"MZ", 415, "UNSUPPORTED_POLICY_FORMAT"),
        ("policy.docx", b"not a real docx", 400, "INVALID_FILE"),
        ("policy.txt", b"has\x00binary", 400, "INVALID_FILE"),
        ("policy.pdf", b"", 400, "INVALID_FILE"),
    ],
)
def test_unsupported_or_fake_policy_files_are_rejected_with_a_clear_code(
    policy_client, embedder, filename, data, expected_status, expected_code  # noqa: F811
):
    client, session = policy_client
    response = client.post(
        "/api/policies/ingest",
        headers=auth(),
        data={"policy_name": "Bad", "version": "v1"},
        files={"file": (filename, data, "application/octet-stream")},
    )
    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code
    assert session.query(PolicyVersion).count() == 0  # nothing half-created
    assert embedder.calls == []
