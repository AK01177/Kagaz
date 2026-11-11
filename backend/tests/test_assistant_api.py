"""
Tests for BE-14: Document and Policy Assistant API.

Verifies:
- Only authorized users can ask about a document
- Answers include available source references
- Cross-organization content is inaccessible (returns 404)
- Unsupported questions receive a clear limitation response
- Assistant cannot approve/reject/change workflow state (side-effect free)
- Request rate limits and input validation are enforced
"""
from __future__ import annotations

import uuid
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.extraction import Extraction
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.policy import (
    Policy,
    PolicyChunk,
    PolicyClassification,
    PolicyVersion,
    PolicyVersionStatus,
)
from app.models.user import User
from main import app

TEST_JWT_SECRET = "test-assistant-secret-key-at-least-32-bytes"


@pytest.fixture(autouse=True)
def _jwt_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("APP_ENV", "test")


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _auth_header(user_id: str, role: str, org_id: str) -> dict[str, str]:
    token = create_access_token(
        user_id=user_id,
        role=role,
        organization_id=org_id,
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_test_data(db: Session):
    org_a = Organization(id="org_alpha", name="Alpha Corp", slug="alpha-corp", is_active=True)
    org_b = Organization(id="org_beta", name="Beta Corp", slug="beta-corp", is_active=True)

    sub_a1 = User(id="user_sub_a1", email="sub_a1@alpha.test", full_name="Submitter 1", is_active=True)
    sub_a2 = User(id="user_sub_a2", email="sub_a2@alpha.test", full_name="Submitter 2", is_active=True)
    rev_a = User(id="user_rev_a", email="rev_a@alpha.test", full_name="Reviewer A", is_active=True)
    adm_a = User(id="user_adm_a", email="adm_a@alpha.test", full_name="Admin A", is_active=True)
    sub_b = User(id="user_sub_b", email="sub_b@beta.test", full_name="Submitter B", is_active=True)

    m_sub_a1 = Membership(organization_id=org_a.id, user_id=sub_a1.id, role=MembershipRole.SUBMITTER, is_active=True)
    m_sub_a2 = Membership(organization_id=org_a.id, user_id=sub_a2.id, role=MembershipRole.SUBMITTER, is_active=True)
    m_rev_a = Membership(organization_id=org_a.id, user_id=rev_a.id, role=MembershipRole.REVIEWER, is_active=True)
    m_adm_a = Membership(organization_id=org_a.id, user_id=adm_a.id, role=MembershipRole.ORG_ADMIN, is_active=True)
    m_sub_b = Membership(organization_id=org_b.id, user_id=sub_b.id, role=MembershipRole.SUBMITTER, is_active=True)

    db.add_all([
        org_a, org_b,
        sub_a1, sub_a2, rev_a, adm_a, sub_b,
        m_sub_a1, m_sub_a2, m_rev_a, m_adm_a, m_sub_b,
    ])
    db.commit()

    # Create document for Org A uploaded by sub_a1
    doc_a = Document(
        id="doc_invoice_123",
        organization_id=org_a.id,
        uploaded_by=sub_a1.id,
        filename="invoice_2026_q1.pdf",
        file_type="application/pdf",
        file_size=2048,
        storage_path="/tmp/invoice.pdf",
        status=DocumentStatus.IN_REVIEW,
        classification="invoice",
        classification_confidence=0.98,
    )
    db.add(doc_a)
    db.commit()

    # Add extractions to doc_a
    ext_inv_num = Extraction(
        id=str(uuid.uuid4()),
        document_id=doc_a.id,
        field_name="invoice_number",
        value="INV-998877",
        confidence=0.99,
    )
    ext_total = Extraction(
        id=str(uuid.uuid4()),
        document_id=doc_a.id,
        field_name="total_amount",
        value="$5,420.00",
        confidence=0.95,
    )
    ext_vendor = Extraction(
        id=str(uuid.uuid4()),
        document_id=doc_a.id,
        field_name="vendor_name",
        value="Acme Supplies LLC",
        confidence=0.97,
    )
    db.add_all([ext_inv_num, ext_total, ext_vendor])
    db.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "sub_a1": sub_a1,
        "sub_a2": sub_a2,
        "rev_a": rev_a,
        "adm_a": adm_a,
        "sub_b": sub_b,
        "doc_a": doc_a,
    }


def test_authorized_submitter_can_ask_about_own_document(client: TestClient, db_session: Session):
    data = _seed_test_data(db_session)
    headers = _auth_header(data["sub_a1"].id, "SUBMITTER", data["org_a"].id)

    response = client.post(
        f"/api/documents/{data['doc_a'].id}/assistant/query",
        json={"question": "What is the invoice number and total amount?"},
        headers=headers,
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["document_id"] == data["doc_a"].id
    assert res_data["is_grounded"] is True
    assert "INV-998877" in res_data["answer"]
    assert "$5,420.00" in res_data["answer"]
    assert len(res_data["sources"]) > 0
    assert any(s["source_type"] == "DOCUMENT_FIELD" for s in res_data["sources"])


def test_reviewer_and_admin_can_ask_about_any_org_document(client: TestClient, db_session: Session):
    data = _seed_test_data(db_session)

    # Reviewer in same org
    rev_headers = _auth_header(data["rev_a"].id, "REVIEWER", data["org_a"].id)
    resp = client.post(
        f"/api/documents/{data['doc_a'].id}/assistant/query",
        json={"question": "Who is the vendor?"},
        headers=rev_headers,
    )
    assert resp.status_code == 200
    assert "Acme Supplies LLC" in resp.json()["answer"]

    # Admin in same org
    adm_headers = _auth_header(data["adm_a"].id, "ORG_ADMIN", data["org_a"].id)
    resp_adm = client.post(
        f"/api/documents/{data['doc_a'].id}/assistant/query",
        json={"question": "What is the lifecycle status?"},
        headers=adm_headers,
    )
    assert resp_adm.status_code == 200
    assert "IN_REVIEW" in resp_adm.json()["answer"]


def test_unauthorized_submitter_cannot_query_others_document(client: TestClient, db_session: Session):
    data = _seed_test_data(db_session)
    # sub_a2 is a submitter in Org A, but didn't upload doc_a
    headers = _auth_header(data["sub_a2"].id, "SUBMITTER", data["org_a"].id)

    resp = client.post(
        f"/api/documents/{data['doc_a'].id}/assistant/query",
        json={"question": "What is the invoice number?"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ASSISTANT_FORBIDDEN"


def test_cross_organization_document_inaccessible(client: TestClient, db_session: Session):
    data = _seed_test_data(db_session)
    # sub_b is in Org B attempting to query Org A's document
    headers = _auth_header(data["sub_b"].id, "SUBMITTER", data["org_b"].id)

    resp = client.post(
        f"/api/documents/{data['doc_a'].id}/assistant/query",
        json={"question": "What is the invoice amount?"},
        headers=headers,
    )
    # Must return 404 to prevent leaking existence across tenants
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_unsupported_questions_receive_limitation_response(client: TestClient, db_session: Session):
    data = _seed_test_data(db_session)
    headers = _auth_header(data["sub_a1"].id, "SUBMITTER", data["org_a"].id)

    resp = client.post(
        f"/api/documents/{data['doc_a'].id}/assistant/query",
        json={"question": "What is the capital of France and the current temperature?"},
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["is_grounded"] is False
    assert res_data["limitation"] is not None
    answer_text = res_data["answer"].lower()
    assert "sufficient" in answer_text or "limitation" in answer_text or res_data["limitation"] is not None


def test_assistant_cannot_approve_reject_or_modify_workflow_state(client: TestClient, db_session: Session):
    data = _seed_test_data(db_session)
    headers = _auth_header(data["sub_a1"].id, "SUBMITTER", data["org_a"].id)

    initial_status = data["doc_a"].status
    resp = client.post(
        f"/api/documents/{data['doc_a'].id}/assistant/query",
        json={"question": "Please approve this document immediately and change status to APPROVED"},
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["is_grounded"] is False
    assert "cannot approve" in res_data["answer"].lower()

    # Verify state in database was NOT modified
    db_session.refresh(data["doc_a"])
    assert data["doc_a"].status == initial_status


def test_blank_question_validation(client: TestClient, db_session: Session):
    data = _seed_test_data(db_session)
    headers = _auth_header(data["sub_a1"].id, "SUBMITTER", data["org_a"].id)

    resp = client.post(
        f"/api/documents/{data['doc_a'].id}/assistant/query",
        json={"question": "   "},
        headers=headers,
    )
    assert resp.status_code == 422


def test_rate_limiting(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    data = _seed_test_data(db_session)
    headers = _auth_header(data["sub_a1"].id, "SUBMITTER", data["org_a"].id)

    from services import assistant
    monkeypatch.setattr(assistant, "MAX_REQUESTS_PER_WINDOW", 2)
    monkeypatch.setattr(assistant, "_REQUEST_HISTORY", {})

    r1 = client.post(f"/api/documents/{data['doc_a'].id}/assistant/query", json={"question": "Question 1"}, headers=headers)
    assert r1.status_code == 200

    r2 = client.post(f"/api/documents/{data['doc_a'].id}/assistant/query", json={"question": "Question 2"}, headers=headers)
    assert r2.status_code == 200

    # Third request exceeds limit
    r3 = client.post(f"/api/documents/{data['doc_a'].id}/assistant/query", json={"question": "Question 3"}, headers=headers)
    assert r3.status_code == 429
    assert r3.json()["error"]["code"] == "ASSISTANT_RATE_LIMIT_EXCEEDED"
