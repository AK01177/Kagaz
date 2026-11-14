"""QA-10 policy retrieval tests against a disposable PostgreSQL database."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.document import Document
from app.models.policy import EMBEDDING_DIMENSION, Policy, PolicyChunk, PolicyVersion, PolicyVersionStatus
from services import policy_retrieval


def vector(first, second):
    return [first, second] + [0.0] * (EMBEDDING_DIMENSION - 2)


@pytest.fixture
def policy_db(monkeypatch):
    database_url = os.getenv("QA10_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set QA10_TEST_DATABASE_URL to a disposable PostgreSQL database with pgvector")
    if make_url(database_url).get_backend_name() != "postgresql":
        pytest.fail("QA10_TEST_DATABASE_URL must use PostgreSQL")

    monkeypatch.setattr(policy_retrieval, "RELEVANCE_THRESHOLD", 0.75)
    engine = create_engine(database_url)
    schema = f"qa10_{uuid4().hex}"
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            if connection.scalar(text("SELECT to_regtype('vector')")) is None:
                pytest.fail("Enable the vector extension in the QA-10 test database first")
            Base.metadata.create_all(connection)
            with Session(connection) as session:
                yield session
            # The connection context rolls back on failures. Roll back on success too.
            connection.rollback()
    finally:
        engine.dispose()


def add_policy_version(db, policy, version_name, status, embedding):
    db.add(policy)
    db.flush()
    filename = f"{policy.organization_id}-{version_name}.pdf"
    source = Document(
        organization_id=policy.organization_id,
        uploaded_by=f"admin-{policy.organization_id}",
        filename=filename,
        file_type="application/pdf",
        file_size=100,
        storage_path=filename,
    )
    db.add(source)
    db.flush()
    version = PolicyVersion(
        policy_id=policy.id, source_document_id=source.id, version=version_name, status=status
    )
    db.add(version)
    db.flush()
    chunk = PolicyChunk(
        policy_version_id=version.id,
        content="Travel expenses require approval.",
        embedding=embedding,
        chunk_index=0,
        page_number=2,
        section="Travel expenses",
        chunk_metadata={"source_document_id": source.id, "source_filename": filename},
    )
    db.add(chunk)
    db.flush()
    return chunk.id


def search(db, organization_id="org-a", embedding=None, domain="finance", document_type="invoice"):
    return policy_retrieval.retrieve_policy_evidence(
        db=db,
        organization_id=organization_id,
        role="ORG_ADMIN",
        embedding=vector(1.0, 0.0) if embedding is None else embedding,
        domain=domain,
        document_type=document_type,
        policy_version=None,
        limit=20,
    )


def finance_policy(organization_id="org-a", active=True, document_type="invoice"):
    return Policy(
        name="Travel Policy",
        organization_id=organization_id,
        domain="finance",
        document_type=document_type,
        is_active=active,
    )


def test_retrieval_returns_only_the_active_version_in_the_callers_organization(policy_db):
    db = policy_db
    policy_a = finance_policy()
    add_policy_version(db, policy_a, "v1", PolicyVersionStatus.ARCHIVED, vector(1.0, 0.0))
    active_a = add_policy_version(db, policy_a, "v2", PolicyVersionStatus.ACTIVE, vector(0.8, 0.6))
    active_b = add_policy_version(
        db, finance_policy("org-b"), "v2", PolicyVersionStatus.ACTIVE, vector(1.0, 0.0)
    )
    inactive_policy = finance_policy(active=False)
    add_policy_version(db, inactive_policy, "v2", PolicyVersionStatus.ACTIVE, vector(1.0, 0.0))

    db.expire_all()
    result_a = search(db)
    result_b = search(db, organization_id="org-b")

    assert result_a.outcome == result_b.outcome == "results"
    assert [row[2].id for row in result_a.rows] == [active_a]
    assert [row[2].id for row in result_b.rows] == [active_b]
    policy, version, chunk, score, source = result_a.rows[0]
    assert policy.organization_id == source.organization_id == "org-a"
    assert version.version == "v2"
    assert chunk.policy_version_id == version.id
    assert version.source_document_id == source.id
    assert chunk.chunk_metadata["source_document_id"] == source.id
    assert chunk.chunk_metadata["source_filename"] == source.filename
    assert chunk.page_number == 2
    assert chunk.section == "Travel expenses"
    assert list(chunk.embedding) == pytest.approx(vector(0.8, 0.6))
    assert score == pytest.approx(0.8)


@pytest.mark.parametrize(
    ("domain", "document_type"), [("hr", "invoice"), ("finance", "transcript")]
)
def test_retrieval_excludes_evidence_outside_requested_filters(policy_db, domain, document_type):
    add_policy_version(
        policy_db, finance_policy(), "v1", PolicyVersionStatus.ACTIVE, vector(1.0, 0.0)
    )
    result = search(policy_db, domain=domain, document_type=document_type)
    assert result.outcome == "no_results"
    assert result.rows == []


def test_retrieval_returns_no_results_when_only_other_organizations_have_evidence(policy_db):
    add_policy_version(
        policy_db, finance_policy("org-b"), "v1", PolicyVersionStatus.ACTIVE, vector(1.0, 0.0)
    )
    result = search(policy_db)
    assert result.outcome == "no_results"
    assert result.rows == []


def test_retrieval_returns_low_relevance_for_eligible_but_unrelated_evidence(policy_db):
    add_policy_version(
        policy_db, finance_policy(), "v1", PolicyVersionStatus.ACTIVE, vector(0.0, 1.0)
    )
    result = search(policy_db)
    assert result.outcome == "low_relevance"
    assert result.rows == []
