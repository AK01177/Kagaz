"""Cross-tenant isolation tests across auth context, documents, policies, workflow, audit, and background jobs."""
from __future__ import annotations

import json
import uuid
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

import pytest
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import create_access_token, get_auth_db
from app.api.routes.documents import router as legacy_documents_router
from app.crud.extraction import (
    create_extractions_bulk,
    delete_extractions_by_document,
    get_document_extractions_summary,
    get_extractions_by_document,
)
from app.crud.policy import list_policy_versions
from app.crud.user import create_user
from app.crud.validation import save_validation_result
from app.db.base import Base
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.membership import Membership, MembershipRole
from app.models.notification import Notification
from app.models.organization import Organization
from app.models.policy import (
    EMBEDDING_DIMENSION,
    Policy,
    PolicyChunk,
    PolicyVersion,
    PolicyVersionStatus,
)
from app.models.workflow import AuditEvent
from app.schemas.extraction import ExtractedField, ExtractionCreate, InvoiceExtraction
from app.schemas.user import UserCreate
from main import app
from services.extraction_persistence import (
    ExtractionPersistenceError,
    persist_extraction_result,
)
from services.policy_ingestion import ingest_policy_version
from services.policy_retrieval import retrieve_policy_evidence
from services.policy_validation import run_policy_validation
from services.upload import UploadError, save_upload
from services.validation import validate_document
from storage.document_storage import DocumentStorage

TEST_JWT_SECRET = "tenant-isolation-test-secret-key-32-bytes"


@pytest.fixture(autouse=True)
def _tenant_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("JWT_ISSUER", "kagaz")
    monkeypatch.setenv("JWT_AUDIENCE", "kagaz-api")
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(tmp_path / "storage"))


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_connection, _connection_record):
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
        engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_auth_db] = lambda: db_session
    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_auth_db, None)


def _auth_header(
    user_id: str,
    organization_id: str,
    role: str,
    *,
    extra_org_header: str | None = None,
) -> dict[str, str]:
    token = create_access_token(
        user_id=user_id,
        role=role,
        organization_id=organization_id,
    )
    headers = {"Authorization": f"Bearer {token}"}
    if extra_org_header is not None:
        headers["X-Organization-Id"] = extra_org_header
    return headers


def _seed_two_tenants(db: Session) -> dict[str, str]:
    org_a_id = str(uuid.uuid4())
    org_b_id = str(uuid.uuid4())
    org_c_id = str(uuid.uuid4())
    org_inactive_id = str(uuid.uuid4())

    db.add_all(
        [
            Organization(id=org_a_id, name="Tenant Alpha", slug=f"alpha-{org_a_id[:8]}", is_active=True),
            Organization(id=org_b_id, name="Tenant Beta", slug=f"beta-{org_b_id[:8]}", is_active=True),
            Organization(id=org_c_id, name="Tenant Gamma", slug=f"gamma-{org_c_id[:8]}", is_active=True),
            Organization(id=org_inactive_id, name="Tenant Inactive", slug=f"inactive-{org_inactive_id[:8]}", is_active=False),
        ]
    )
    db.flush()

    users = [
        ("usr_multi", "multi@alpha.test", "Multi Member"),
        ("usr_a_sub", "sub@alpha.test", "Alpha Submitter"),
        ("usr_a_rev", "rev@alpha.test", "Alpha Reviewer"),
        ("usr_a_adm", "adm@alpha.test", "Alpha Admin"),
        ("usr_b_rev", "rev@beta.test", "Beta Reviewer"),
        ("usr_b_adm", "adm@beta.test", "Beta Admin"),
    ]
    for uid, email, name in users:
        create_user(
            db,
            UserCreate(
                id=uid,
                email=email,
                full_name=name,
                password="StrongTenantPassword!9",
                is_active=True,
            ),
        )

    db.add_all(
        [
            Membership(user_id="usr_multi", organization_id=org_a_id, role=MembershipRole.SUBMITTER, is_active=True),
            Membership(user_id="usr_multi", organization_id=org_b_id, role=MembershipRole.REVIEWER, is_active=True),
            Membership(user_id="usr_multi", organization_id=org_c_id, role=MembershipRole.ORG_ADMIN, is_active=False),
            Membership(user_id="usr_multi", organization_id=org_inactive_id, role=MembershipRole.ORG_ADMIN, is_active=True),
            Membership(user_id="usr_a_sub", organization_id=org_a_id, role=MembershipRole.SUBMITTER, is_active=True),
            Membership(user_id="usr_a_rev", organization_id=org_a_id, role=MembershipRole.REVIEWER, is_active=True),
            Membership(user_id="usr_a_adm", organization_id=org_a_id, role=MembershipRole.ORG_ADMIN, is_active=True),
            Membership(user_id="usr_b_rev", organization_id=org_b_id, role=MembershipRole.REVIEWER, is_active=True),
            Membership(user_id="usr_b_adm", organization_id=org_b_id, role=MembershipRole.ORG_ADMIN, is_active=True),
        ]
    )
    db.commit()

    return {
        "org_a": org_a_id,
        "org_b": org_b_id,
        "org_c": org_c_id,
        "org_inactive": org_inactive_id,
        "multi": "usr_multi",
        "a_sub": "usr_a_sub",
        "a_rev": "usr_a_rev",
        "a_adm": "usr_a_adm",
        "b_rev": "usr_b_rev",
        "b_adm": "usr_b_adm",
    }


def _write_doc_artifacts(
    storage: DocumentStorage,
    doc_id: str,
    organization_id: str | None,
    *,
    category: str = "financial",
    extra_fields: dict | None = None,
) -> None:
    storage.base_dir.mkdir(parents=True, exist_ok=True)
    (storage.base_dir / "metadata").mkdir(parents=True, exist_ok=True)
    file_path = storage.base_dir / f"{doc_id}.pdf"
    file_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")
    metadata: dict = {
        "document_id": doc_id,
        "filename": f"{doc_id}.pdf",
        "file_type": "application/pdf",
        "status": "EXTRACTED",
        "category": category,
        "confidence": 0.95,
        "extracted_fields": extra_fields or {"invoice_number": "INV-SECRET-B", "total_amount": "9000", "supplier_name": "Beta Corp"},
        "extracted_confidence": {"invoice_number": 0.99, "total_amount": 0.99, "supplier_name": 0.99},
    }
    if organization_id is not None:
        metadata["organization_id"] = organization_id
    (storage.base_dir / "metadata" / f"{doc_id}.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )


class TestMembershipAndActiveOrganizationContext:
    def test_memberships_list_and_context_switching_enforce_db_membership(
        self, client: TestClient, db_session: Session
    ) -> None:
        ids = _seed_two_tenants(db_session)

        # Default active context from JWT (Org A -> SUBMITTER)
        me_a = client.get("/api/auth/me", headers=_auth_header(ids["multi"], ids["org_a"], "SUBMITTER"))
        assert me_a.status_code == 200
        assert me_a.json()["organization_id"] == ids["org_a"]
        assert me_a.json()["role"] == "SUBMITTER"

        mem_res = client.get(
            "/api/auth/memberships",
            headers=_auth_header(ids["multi"], ids["org_a"], "SUBMITTER"),
        )
        assert mem_res.status_code == 200
        body = mem_res.json()
        assert body["active_organization_id"] == ids["org_a"]
        org_roles = {m["organization_id"]: m["role"] for m in body["memberships"]}
        assert org_roles == {ids["org_a"]: "SUBMITTER", ids["org_b"]: "REVIEWER"}

        # Switch active context to Org B via X-Organization-Id -> server resolves REVIEWER role
        me_b = client.get(
            "/api/auth/me",
            headers=_auth_header(ids["multi"], ids["org_a"], "SUBMITTER", extra_org_header=ids["org_b"]),
        )
        assert me_b.status_code == 200
        assert me_b.json()["organization_id"] == ids["org_b"]
        assert me_b.json()["role"] == "REVIEWER"

        # Switching into org with inactive membership, inactive org, or no membership fails 403
        for forbidden_org in (ids["org_c"], ids["org_inactive"], str(uuid.uuid4()), "   "):
            denied = client.get(
                "/api/auth/me",
                headers=_auth_header(ids["multi"], ids["org_a"], "SUBMITTER", extra_org_header=forbidden_org),
            )
            assert denied.status_code == 403
            assert denied.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"

    def test_stateless_mode_rejects_unverified_org_header_switch(self) -> None:
        app.dependency_overrides.pop(get_auth_db, None)
        with TestClient(app) as tc:
            headers = _auth_header("usr_x", "org_a", "REVIEWER", extra_org_header="org_b")
            res = tc.get("/api/auth/me", headers=headers)
            assert res.status_code == 403
            assert res.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"


class TestDocumentAndFileRouteTenantIsolation:
    def test_cross_tenant_document_routes_reject_with_403(
        self, client: TestClient, db_session: Session
    ) -> None:
        ids = _seed_two_tenants(db_session)
        doc_b_id = f"doc_{uuid.uuid4().hex}"
        storage = DocumentStorage()
        _write_doc_artifacts(storage, doc_b_id, ids["org_b"])

        doc_b = Document(
            id=doc_b_id,
            organization_id=ids["org_b"],
            uploaded_by=ids["b_rev"],
            filename="beta-secret.pdf",
            file_type="application/pdf",
            file_size=512,
            storage_path=str((storage.base_dir / f"{doc_b_id}.pdf").resolve()),
            status=DocumentStatus.EXTRACTED,
            classification="financial",
        )
        db_session.add(doc_b)
        db_session.flush()
        create_extractions_bulk(
            db_session,
            doc_b_id,
            [ExtractionCreate(field_name="invoice_number", value="BETA-999", confidence=0.99)],
        )
        save_validation_result(
            db_session,
            document_id=doc_b_id,
            organization_id=ids["org_b"],
            status="PASS",
        )

        # Caller in Org A attempts to guess Doc B's ID across all document endpoints
        rev_a = _auth_header(ids["a_rev"], ids["org_a"], "REVIEWER")
        sub_a = _auth_header(ids["a_sub"], ids["org_a"], "SUBMITTER")

        assert client.get(f"/api/documents/{doc_b_id}", headers=rev_a).status_code == 403
        file_res = client.get(f"/api/documents/{doc_b_id}/file", headers=rev_a)
        assert file_res.status_code == 403
        assert b"%PDF" not in file_res.content

        assert (
            client.patch(
                f"/api/documents/{doc_b_id}/classification",
                headers=rev_a,
                json={"category": "hr_documents", "notes": "cross-tenant tamper"},
            ).status_code
            == 403
        )
        assert client.get(f"/api/documents/{doc_b_id}/extract", headers=rev_a).status_code == 403
        assert client.post(f"/api/documents/{doc_b_id}/extract", headers=rev_a).status_code == 403
        assert client.post(f"/api/documents/{doc_b_id}/classify", headers=rev_a).status_code == 403
        assert client.post(f"/api/documents/{doc_b_id}/validate", headers=sub_a).status_code == 403
        assert client.get(f"/api/documents/{doc_b_id}/validate", headers=sub_a).status_code == 403
        assert client.post(f"/api/documents/{doc_b_id}/validate-policy", headers=rev_a).status_code in (403, 404)

        # Verify DB-only document & extraction lookups also stay isolated without metadata JSON
        db_only_doc_b = f"doc_{uuid.uuid4().hex}"
        db_session.add(
            Document(
                id=db_only_doc_b,
                organization_id=ids["org_b"],
                uploaded_by=ids["b_rev"],
                filename="beta-db-only.pdf",
                file_type="application/pdf",
                file_size=128,
                storage_path="/tmp/beta-db-only.pdf",
                status=DocumentStatus.EXTRACTED,
                classification="financial",
            )
        )
        db_session.flush()
        create_extractions_bulk(
            db_session,
            db_only_doc_b,
            [ExtractionCreate(field_name="supplier_name", value="Hidden Beta Vendor", confidence=0.9)],
        )
        assert client.get(f"/api/documents/{db_only_doc_b}/extract", headers=rev_a).status_code == 403
        assert get_document_extractions_summary(db_session, db_only_doc_b, organization_id=ids["org_a"]) is None
        assert get_extractions_by_document(db_session, db_only_doc_b, organization_id=ids["org_a"]) == []
        assert delete_extractions_by_document(db_session, db_only_doc_b, organization_id=ids["org_a"]) == 0
        assert len(get_extractions_by_document(db_session, db_only_doc_b, organization_id=ids["org_b"])) == 1

    def test_orphaned_document_without_organization_fails_closed(
        self, client: TestClient, db_session: Session
    ) -> None:
        ids = _seed_two_tenants(db_session)
        orphan_id = f"doc_{uuid.uuid4().hex}"
        storage = DocumentStorage()
        _write_doc_artifacts(storage, orphan_id, organization_id=None)

        rev_a = _auth_header(ids["a_rev"], ids["org_a"], "REVIEWER")
        sub_a = _auth_header(ids["a_sub"], ids["org_a"], "SUBMITTER")

        assert client.get(f"/api/documents/{orphan_id}", headers=rev_a).status_code == 403
        assert client.get(f"/api/documents/{orphan_id}/file", headers=rev_a).status_code == 403
        assert client.get(f"/api/documents/{orphan_id}/extract", headers=rev_a).status_code == 403
        assert (
            client.patch(
                f"/api/documents/{orphan_id}/classification",
                headers=rev_a,
                json={"category": "financial"},
            ).status_code
            == 403
        )
        assert client.post(f"/api/documents/{orphan_id}/extract", headers=rev_a).status_code == 403
        assert client.post(f"/api/documents/{orphan_id}/classify", headers=rev_a).status_code == 403
        assert client.post(f"/api/documents/{orphan_id}/validate", headers=sub_a).status_code == 403

    def test_legacy_document_metadata_route_ignores_query_org_and_enforces_token_org(
        self, db_session: Session
    ) -> None:
        ids = _seed_two_tenants(db_session)
        doc_a_id = str(uuid.uuid4())
        doc_b_id = str(uuid.uuid4())
        db_session.add_all(
            [
                Document(
                    id=doc_a_id,
                    organization_id=ids["org_a"],
                    uploaded_by=ids["a_rev"],
                    filename="alpha.pdf",
                    file_type="application/pdf",
                    file_size=100,
                    storage_path="/tmp/alpha.pdf",
                    status=DocumentStatus.UPLOADED,
                ),
                Document(
                    id=doc_b_id,
                    organization_id=ids["org_b"],
                    uploaded_by=ids["b_rev"],
                    filename="beta.pdf",
                    file_type="application/pdf",
                    file_size=100,
                    storage_path="/tmp/beta.pdf",
                    status=DocumentStatus.UPLOADED,
                ),
            ]
        )
        db_session.commit()

        legacy_app = FastAPI()
        legacy_app.include_router(legacy_documents_router)
        legacy_app.dependency_overrides[get_db] = lambda: db_session
        legacy_app.dependency_overrides[get_auth_db] = lambda: db_session

        rev_a = _auth_header(ids["a_rev"], ids["org_a"], "REVIEWER")
        with TestClient(legacy_app) as tc:
            # Passing ?organization_id=<org_b> cannot bypass token-resolved org_a
            denied = tc.get(f"/documents/{doc_b_id}?organization_id={ids['org_b']}", headers=rev_a)
            assert denied.status_code == 404
            allowed = tc.get(f"/documents/{doc_a_id}", headers=rev_a)
            assert allowed.status_code == 200
            assert str(allowed.json()["id"]) == doc_a_id


class TestPolicyWorkflowAssistantAuditAndNotificationIsolation:
    def test_policy_crud_versions_and_vector_retrieval_enforce_organization_scope(
        self, client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ids = _seed_two_tenants(db_session)
        src_a = Document(
            id=f"doc_{uuid.uuid4().hex}",
            organization_id=ids["org_a"],
            uploaded_by=ids["a_adm"],
            filename="pol-a.pdf",
            file_type="application/pdf",
            file_size=120,
            storage_path="/tmp/pol-a.pdf",
            status=DocumentStatus.UPLOADED,
        )
        src_b = Document(
            id=f"doc_{uuid.uuid4().hex}",
            organization_id=ids["org_b"],
            uploaded_by=ids["b_adm"],
            filename="pol-b.pdf",
            file_type="application/pdf",
            file_size=120,
            storage_path="/tmp/pol-b.pdf",
            status=DocumentStatus.UPLOADED,
        )
        pol_a = Policy(
            id=f"pol_{uuid.uuid4().hex}",
            organization_id=ids["org_a"],
            name="Alpha Travel Policy",
            domain="financial",
            content="Alpha receipts require approval above $500.",
            is_active=True,
        )
        pol_b = Policy(
            id=f"pol_{uuid.uuid4().hex}",
            organization_id=ids["org_b"],
            name="Beta Confidential Policy",
            domain="financial",
            content="Beta secret threshold $99999.",
            is_active=True,
        )
        db_session.add_all([src_a, src_b, pol_a, pol_b])
        db_session.flush()

        ver_a = PolicyVersion(
            policy_id=pol_a.id,
            source_document_id=src_a.id,
            version="v1.0",
            content="Alpha v1",
            status=PolicyVersionStatus.ACTIVE,
        )
        ver_b = PolicyVersion(
            policy_id=pol_b.id,
            source_document_id=src_b.id,
            version="v1.0",
            content="Beta v1",
            status=PolicyVersionStatus.ACTIVE,
        )
        db_session.add_all([ver_a, ver_b])
        db_session.flush()

        vec = [0.5] + [0.0] * (EMBEDDING_DIMENSION - 1)
        db_session.add_all(
            [
                PolicyChunk(
                    policy_version_id=ver_a.id,
                    content="Alpha policy rule chunk.",
                    embedding=vec,
                    chunk_index=0,
                    chunk_metadata={"organization_id": ids["org_a"]},
                ),
                PolicyChunk(
                    policy_version_id=ver_b.id,
                    content="Beta top secret policy chunk.",
                    embedding=vec,
                    chunk_index=0,
                    chunk_metadata={"organization_id": ids["org_b"]},
                ),
            ]
        )
        db_session.commit()

        sub_a = _auth_header(ids["a_sub"], ids["org_a"], "SUBMITTER")
        rev_a = _auth_header(ids["a_rev"], ids["org_a"], "REVIEWER")
        adm_a = _auth_header(ids["a_adm"], ids["org_a"], "ORG_ADMIN")
        # CRUD endpoints never expose Org B policies
        assert client.get(f"/api/policies/{pol_b.id}", headers=sub_a).status_code == 404
        assert (
            client.put(
                f"/api/policies/{pol_b.id}",
                headers=adm_a,
                json={"name": "Hijacked"},
            ).status_code
            == 404
        )
        assert client.delete(f"/api/policies/{pol_b.id}", headers=adm_a).status_code == 404
        assert client.get(f"/api/policies/{pol_b.id}/versions", headers=adm_a).status_code == 404
        assert list_policy_versions(db_session, pol_b.id, organization_id=ids["org_a"]) == []

        # Retrieval endpoint passes server-verified organization_id to vector retrieval
        observed_calls: list[tuple[str, str]] = []

        def _fake_retrieve_policy_evidence(
            db, organization_id, role, query_embedding, *_args, **_kwargs
        ):
            observed_calls.append((organization_id, role))
            rows = (
                db.query(Policy, PolicyVersion, PolicyChunk, Document)
                .join(PolicyVersion, PolicyVersion.policy_id == Policy.id)
                .join(PolicyChunk, PolicyChunk.policy_version_id == PolicyVersion.id)
                .join(Document, Document.id == PolicyVersion.source_document_id)
                .filter(
                    Policy.organization_id == organization_id,
                    Document.organization_id == organization_id,
                )
                .all()
            )
            return SimpleNamespace(
                outcome="results" if rows else "no_results",
                rows=[(p, v, c, 0.95, d) for p, v, c, d in rows],
            )

        monkeypatch.setattr(
            "app.api.routes.policies.create_query_embedding",
            lambda _q: vec,
        )
        monkeypatch.setattr(
            "app.api.routes.policies.retrieve_policy_evidence",
            _fake_retrieve_policy_evidence,
        )
        ret = client.post(
            "/api/policies/retrieve",
            headers=rev_a,
            json={"query": "policy rule", "limit": 5},
        )
        assert ret.status_code == 200
        assert observed_calls == [(ids["org_a"], "REVIEWER")]
        contents = [c["content"] for c in ret.json()["results"]]
        assert contents == ["Alpha policy rule chunk."]

    def test_workflow_assistant_notifications_and_audit_isolate_tenants(
        self, client: TestClient, db_session: Session
    ) -> None:
        ids = _seed_two_tenants(db_session)
        doc_b = Document(
            id=f"doc_{uuid.uuid4().hex}",
            organization_id=ids["org_b"],
            uploaded_by=ids["b_rev"],
            filename="beta-workflow.pdf",
            file_type="application/pdf",
            file_size=250,
            storage_path="/tmp/beta-workflow.pdf",
            status=DocumentStatus.IN_REVIEW,
            classification="financial",
            assigned_reviewer_id=ids["b_rev"],
        )
        db_session.add(doc_b)
        db_session.flush()
        db_session.add(
            AuditEvent(
                document_id=doc_b.id,
                organization_id=ids["org_b"],
                event_type="DOCUMENT_SUBMITTED",
                actor_id=ids["b_rev"],
                actor_type="USER",
                actor_role="REVIEWER",
                from_status="EXTRACTED",
                to_status="IN_REVIEW",
                details={"note": "beta internal"},
            )
        )
        notif_b = Notification(
            organization_id=ids["org_b"],
            recipient_user_id=ids["a_rev"],
            notification_type="ASSIGNED",
            title="Beta secret notification",
            body="Should not leak across org boundary",
            document_id=doc_b.id,
            is_read=False,
        )
        db_session.add(notif_b)
        db_session.commit()

        rev_a = _auth_header(ids["a_rev"], ids["org_a"], "REVIEWER")

        # Review queue contains nothing from Org B
        queue_res = client.get("/api/documents/workflow/review-queue", headers=rev_a)
        assert queue_res.status_code == 200
        assert queue_res.json()["items"] == []

        # Guessing Doc B's ID on workflow, assistant, or audit routes returns 404/403
        assert client.get(f"/api/documents/{doc_b.id}/workflow", headers=rev_a).status_code == 404
        assert client.get(f"/api/documents/{doc_b.id}/review", headers=rev_a).status_code == 404
        assert (
            client.post(
                f"/api/documents/{doc_b.id}/comments",
                headers=rev_a,
                json={"comment": "cross-org snooping"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/documents/{doc_b.id}/approve",
                headers=rev_a,
                json={"reason": "cross-org approval"},
            ).status_code
            == 403
        )
        assert client.get(f"/api/audit/{doc_b.id}", headers=rev_a).status_code == 404
        assert (
            client.post(
                f"/api/documents/{doc_b.id}/assistant",
                headers=rev_a,
                json={"question": "Summarize this document"},
            ).status_code
            in (403, 404)
        )

        # Notifications are scoped by active organization_id even for matching user_id
        notif_list = client.get("/api/notifications", headers=rev_a)
        assert notif_list.status_code == 200
        assert notif_list.json()["items"] == []
        assert client.patch(f"/api/notifications/{notif_b.id}/read", headers=rev_a).status_code == 404


class TestBackgroundJobAndServiceOrganizationVerification:
    def test_policy_ingestion_rejects_mismatched_org_or_cross_org_source_doc(
        self, db_session: Session
    ) -> None:
        ids = _seed_two_tenants(db_session)
        src_a = Document(
            id=f"doc_{uuid.uuid4().hex}",
            organization_id=ids["org_a"],
            uploaded_by=ids["a_adm"],
            filename="alpha-src.pdf",
            file_type="application/pdf",
            file_size=120,
            storage_path="/tmp/alpha-src.pdf",
            status=DocumentStatus.UPLOADED,
        )
        src_b = Document(
            id=f"doc_{uuid.uuid4().hex}",
            organization_id=ids["org_b"],
            uploaded_by=ids["b_adm"],
            filename="beta-src.pdf",
            file_type="application/pdf",
            file_size=120,
            storage_path="/tmp/beta-src.pdf",
            status=DocumentStatus.UPLOADED,
        )
        pol_b = Policy(
            id=f"pol_{uuid.uuid4().hex}",
            organization_id=ids["org_b"],
            name="Beta Policy",
            domain="financial",
            content="Beta",
            is_active=True,
        )
        db_session.add_all([src_a, src_b, pol_b])
        db_session.flush()

        ver_mismatch_expected = PolicyVersion(
            policy_id=pol_b.id,
            source_document_id=src_b.id,
            version="v1.0",
            status=PolicyVersionStatus.PROCESSING,
        )
        ver_cross_org_source = PolicyVersion(
            policy_id=pol_b.id,
            source_document_id=src_a.id,
            version="v1.1",
            status=PolicyVersionStatus.PROCESSING,
        )
        db_session.add_all([ver_mismatch_expected, ver_cross_org_source])
        db_session.commit()

        storage = DocumentStorage()

        chunks_1 = ingest_policy_version(
            db_session,
            pol_b,
            ver_mismatch_expected,
            "beta-src.pdf",
            storage,
            expected_organization_id=ids["org_a"],
        )
        assert chunks_1 == 0
        db_session.refresh(ver_mismatch_expected)
        assert ver_mismatch_expected.status == PolicyVersionStatus.FAILED
        assert "organization context mismatch" in (ver_mismatch_expected.ingestion_error or "").lower()

        chunks_2 = ingest_policy_version(
            db_session,
            pol_b,
            ver_cross_org_source,
            "alpha-src.pdf",
            storage,
            expected_organization_id=ids["org_b"],
        )
        assert chunks_2 == 0
        db_session.refresh(ver_cross_org_source)
        assert ver_cross_org_source.status == PolicyVersionStatus.FAILED
        assert "source document" in (ver_cross_org_source.ingestion_error or "").lower()

    def test_validation_extraction_and_upload_services_fail_closed_on_org_mismatch(
        self, db_session: Session
    ) -> None:
        ids = _seed_two_tenants(db_session)
        doc_b = Document(
            id=f"doc_{uuid.uuid4().hex}",
            organization_id=ids["org_b"],
            uploaded_by=ids["b_rev"],
            filename="beta.pdf",
            file_type="application/pdf",
            file_size=120,
            storage_path="/tmp/beta.pdf",
            status=DocumentStatus.EXTRACTED,
            classification="financial",
        )
        pol_b = Policy(
            id=f"pol_{uuid.uuid4().hex}",
            organization_id=ids["org_b"],
            name="Beta Policy",
            domain="financial",
            content="Max $100",
            is_active=True,
        )
        db_session.add_all([doc_b, pol_b])
        db_session.commit()

        # Background validation rejects mismatched document org or policy org
        with pytest.raises(PermissionError):
            validate_document(
                document_id=doc_b.id,
                organization_id=ids["org_a"],
                domain="financial",
                extracted_fields={"invoice_number": "INV-1", "total_amount": "50", "supplier_name": "Acme"},
                db=db_session,
            )

        with pytest.raises(PermissionError):
            validate_document(
                document_id="doc_unpersisted",
                organization_id=ids["org_a"],
                domain="financial",
                policy=pol_b,
                extracted_fields={"invoice_number": "INV-1", "total_amount": "50", "supplier_name": "Acme"},
            )

        # Policy validation runner rejects cross-org document
        with pytest.raises(Exception) as exc_info:
            run_policy_validation(
                db_session,
                doc_b,
                {"sub": ids["a_rev"], "organization_id": ids["org_a"], "role": "REVIEWER"},
            )
        assert getattr(exc_info.value, "status_code", None) == 403

        # Extraction persistence rejects mismatched org context
        extraction = InvoiceExtraction(
            invoice_number=ExtractedField(value="INV-X", confidence=0.95),
            total_amount=ExtractedField(value=50.0, confidence=0.95),
            supplier_name=ExtractedField(value="Vendor", confidence=0.95),
        )
        with pytest.raises(ExtractionPersistenceError):
            persist_extraction_result(
                db_session,
                doc_b.id,
                extraction,
                organization_id=ids["org_a"],
            )

        # Upload service rejects missing organization context instead of falling back to default_org
        fake_upload = UploadFile(filename="doc.pdf", file=BytesIO(b"%PDF-1.4\n%%EOF"))
        with pytest.raises(UploadError) as upload_exc:
            save_upload(fake_upload, DocumentStorage(), user={"sub": "usr_1"}, db=db_session)
        assert upload_exc.value.status_code == 403
