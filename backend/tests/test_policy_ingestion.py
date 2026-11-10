import io
import time

import jwt
import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.policy import Policy, PolicyVersion, PolicyVersionStatus
from main import app


TEST_SECRET = "policy-ingestion-test-secret-not-for-production"


def _token(organization_id: str, role: str = "ORG_ADMIN") -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": f"admin-{organization_id}",
            "role": role,
            "organization_id": organization_id,
            "active": True,
            "iss": "kagaz",
            "aud": "kagaz-api",
            "iat": now,
            "exp": now + 300,
        },
        TEST_SECRET,
        algorithm="HS256",
    )


def _pdf(text: str = "Policy clause: expenses require approval.") -> bytes:
    stream = io.BytesIO()
    document = canvas.Canvas(stream)
    document.drawString(72, 750, text)
    document.save()
    return stream.getvalue()


def _raise_embedding_error(chunks):
    raise RuntimeError("provider details stay private")


@pytest.fixture
def policy_client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(tmp_path / "documents"))
    engine = create_engine(f"sqlite:///{tmp_path / 'policy.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as client:
        yield client, session
    app.dependency_overrides.pop(get_db, None)
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_org_admin_ingests_policy_and_saves_chunk_metadata(policy_client, monkeypatch):
    client, session = policy_client
    monkeypatch.setattr(
        "services.policy_ingestion.extract_text",
        lambda document_id, storage: "Policy clause: expenses require approval.",
    )
    monkeypatch.setattr(
        "services.policy_ingestion.create_embeddings",
        lambda chunks: [[0.0] * 1536 for _ in chunks],
    )

    response = client.post(
        "/api/policies/ingest",
        headers={"Authorization": f"Bearer {_token('org-a')}"},
        data={"policy_name": "Expense Policy", "version": "v1", "domain": "finance"},
        files={"file": ("expense-policy.pdf", _pdf(), "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["chunk_count"] == 1
    chunk = session.query(Policy).filter_by(id=body["policy_id"]).first().versions[0].chunks[0]
    assert chunk.chunk_metadata["organization_id"] == "org-a"
    assert chunk.chunk_metadata["domain"] == "finance"
    assert chunk.chunk_metadata["version"] == "v1"
    assert chunk.chunk_metadata["source_document_id"] == body["source_document_id"]

    replacement = client.post(
        "/api/policies/ingest",
        headers={"Authorization": f"Bearer {_token('org-a')}"},
        data={"policy_name": "Expense Policy", "version": "v2", "domain": "finance"},
        files={"file": ("expense-policy-v2.pdf", _pdf("Updated policy text."), "application/pdf")},
    )
    assert replacement.status_code == 201
    versions = session.query(PolicyVersion).filter_by(policy_id=body["policy_id"]).all()
    assert {item.version: item.status.value for item in versions} == {
        "v1": "ARCHIVED",
        "v2": "ACTIVE",
    }


def test_empty_extraction_is_visible_and_retryable(policy_client, monkeypatch):
    client, session = policy_client
    monkeypatch.setattr("services.policy_ingestion.extract_text", lambda document_id, storage: "  ")

    response = client.post(
        "/api/policies/ingest",
        headers={"Authorization": f"Bearer {_token('org-a')}"},
        data={"policy_name": "Empty Policy", "version": "v1"},
        files={"file": ("empty-policy.pdf", _pdf(), "application/pdf")},
    )
    body = response.json()

    assert response.status_code == 201
    assert body["status"] == "FAILED"
    assert "No readable text" in body["ingestion_error"]

    versions = client.get(
        f"/api/policies/{body['policy_id']}/versions",
        headers={"Authorization": f"Bearer {_token('org-a')}"},
    )
    assert versions.status_code == 200
    assert versions.json()[0]["status"] == "FAILED"

    monkeypatch.setattr(
        "services.policy_ingestion.extract_text",
        lambda document_id, storage: "Policy text after retry.",
    )
    monkeypatch.setattr(
        "services.policy_ingestion.create_embeddings",
        lambda chunks: [[0.0] * 1536 for _ in chunks],
    )
    retry = client.post(
        f"/api/policies/{body['policy_id']}/versions/{body['policy_version_id']}/retry",
        headers={"Authorization": f"Bearer {_token('org-a')}"},
    )
    assert retry.status_code == 200
    assert retry.json()["status"] == "ACTIVE"
    assert session.query(PolicyVersion).filter_by(id=body["policy_version_id"]).count() == 1


def test_unexpected_ingestion_error_is_visible_and_retryable(policy_client, monkeypatch):
    client, session = policy_client
    monkeypatch.setattr(
        "services.policy_ingestion.extract_text",
        lambda document_id, storage: "Policy text before an embedding error.",
    )
    monkeypatch.setattr(
        "services.policy_ingestion.create_embeddings",
        _raise_embedding_error,
    )

    response = client.post(
        "/api/policies/ingest",
        headers={"Authorization": f"Bearer {_token('org-a')}"},
        data={"policy_name": "Retry Policy", "version": "v1"},
        files={"file": ("retry-policy.pdf", _pdf(), "application/pdf")},
    )
    body = response.json()

    assert response.status_code == 201
    assert body["status"] == "FAILED"
    assert body["ingestion_error"] == "Policy ingestion failed unexpectedly."
    assert "provider details stay private" not in body["ingestion_error"]

    monkeypatch.setattr(
        "services.policy_ingestion.create_embeddings",
        lambda chunks: [[0.0] * 1536 for _ in chunks],
    )
    retry = client.post(
        f"/api/policies/{body['policy_id']}/versions/{body['policy_version_id']}/retry",
        headers={"Authorization": f"Bearer {_token('org-a')}"},
    )

    assert retry.status_code == 200
    assert retry.json()["status"] == "ACTIVE"
    assert session.query(PolicyVersion).filter_by(id=body["policy_version_id"]).count() == 1


def test_policy_versions_are_hidden_from_other_organizations(policy_client):
    client, session = policy_client
    source = Document(
        id="doc_org_b",
        organization_id="org-b",
        uploaded_by="admin-org-b",
        filename="private-policy.pdf",
        file_type="application/pdf",
        file_size=10,
        storage_path="private-policy.pdf",
        status=DocumentStatus.UPLOADED,
    )
    policy = Policy(
        organization_id="org-b",
        name="Private Policy",
        domain="security",
    )
    session.add_all([source, policy])
    session.flush()
    version = PolicyVersion(
        policy_id=policy.id,
        source_document_id=source.id,
        version="v1",
        status=PolicyVersionStatus.FAILED,
        ingestion_error="No readable text was extracted from the PDF.",
    )
    session.add(version)
    session.commit()
    headers = {"Authorization": f"Bearer {_token('org-a')}"}

    listing = client.get(f"/api/policies/{policy.id}/versions", headers=headers)
    retry = client.post(
        f"/api/policies/{policy.id}/versions/{version.id}/retry",
        headers=headers,
    )

    assert listing.status_code == 404
    assert retry.status_code == 404


def test_only_org_admin_can_ingest_policy(policy_client):
    client, _ = policy_client
    response = client.post(
        "/api/policies/ingest",
        headers={"Authorization": f"Bearer {_token('org-a', role='REVIEWER')}"},
        data={"policy_name": "Expense Policy", "version": "v1"},
        files={"file": ("expense-policy.pdf", _pdf(), "application/pdf")},
    )
    assert response.status_code == 403
