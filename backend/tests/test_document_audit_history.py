"""Tests for trustworthy, immutable, organization-scoped document audit history."""
from __future__ import annotations

import io
import json
import tempfile
import uuid
from pathlib import Path
from typing import Iterator

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.policy_validation import PolicyValidationRun
from app.models.user import User
from app.models.workflow import AuditEvent, AuditImmutabilityError
from main import app
from services.audit import record_audit_event
from app.schemas.extraction import InvoiceExtraction
from services.classification import ClassificationResult, DocumentCategory
from services.upload import save_upload
from services.validation import validate_document
from storage.document_storage import DocumentStorage

TEST_JWT_SECRET = "test-audit-history-secret-key-at-least-32-bytes"


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
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def _auth_header(user_id: str, org_id: str, role: str) -> dict[str, str]:
    token = create_access_token(user_id=user_id, role=role, organization_id=org_id)
    return {"Authorization": f"Bearer {token}"}


def _make_pdf_bytes(text: str = "Invoice INV-777 Supplier Acme Total $450.00") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 750, text)
    c.save()
    return buf.getvalue()


def _seed_org_and_users(db: Session) -> dict[str, str]:
    org_a = str(uuid.uuid4())
    org_b = str(uuid.uuid4())
    sub_1 = str(uuid.uuid4())
    sub_2 = str(uuid.uuid4())
    rev_1 = str(uuid.uuid4())
    rev_2 = str(uuid.uuid4())
    approver = str(uuid.uuid4())
    auditor_a = str(uuid.uuid4())
    auditor_b = str(uuid.uuid4())

    db.add_all([
        Organization(id=org_a, name="Acme Audit", slug=f"acme-{org_a[:6]}"),
        Organization(id=org_b, name="Beta Audit", slug=f"beta-{org_b[:6]}"),
        User(id=sub_1, email=f"s1-{sub_1[:6]}@acme.test", full_name="Submitter 1", is_active=True),
        User(id=sub_2, email=f"s2-{sub_2[:6]}@acme.test", full_name="Submitter 2", is_active=True),
        User(id=rev_1, email=f"r1-{rev_1[:6]}@acme.test", full_name="Reviewer 1", is_active=True),
        User(id=rev_2, email=f"r2-{rev_2[:6]}@acme.test", full_name="Reviewer 2", is_active=True),
        User(id=approver, email=f"app-{approver[:6]}@acme.test", full_name="Approver", is_active=True),
        User(id=auditor_a, email=f"audA-{auditor_a[:6]}@acme.test", full_name="Auditor A", is_active=True),
        User(id=auditor_b, email=f"audB-{auditor_b[:6]}@beta.test", full_name="Auditor B", is_active=True),
    ])
    db.flush()
    db.add_all([
        Membership(organization_id=org_a, user_id=sub_1, role=MembershipRole.SUBMITTER, is_active=True),
        Membership(organization_id=org_a, user_id=sub_2, role=MembershipRole.SUBMITTER, is_active=True),
        Membership(organization_id=org_a, user_id=rev_1, role=MembershipRole.REVIEWER, is_active=True),
        Membership(organization_id=org_a, user_id=rev_2, role=MembershipRole.REVIEWER, is_active=True),
        Membership(organization_id=org_a, user_id=approver, role=MembershipRole.APPROVER, is_active=True),
        Membership(organization_id=org_a, user_id=auditor_a, role=MembershipRole.AUDITOR, is_active=True),
        Membership(organization_id=org_b, user_id=auditor_b, role=MembershipRole.AUDITOR, is_active=True),
    ])
    db.commit()
    return {
        "org_a": org_a,
        "org_b": org_b,
        "sub_1": sub_1,
        "sub_2": sub_2,
        "rev_1": rev_1,
        "rev_2": rev_2,
        "approver": approver,
        "auditor_a": auditor_a,
        "auditor_b": auditor_b,
    }


class TestFullAuditLifecycleAndChronology:
    def test_records_processing_and_workflow_events_in_chronological_order(
        self, client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        actors = _seed_org_and_users(db_session)

        monkeypatch.setattr(
            "services.upload.classify_document",
            lambda text: ClassificationResult(category=DocumentCategory.FINANCIAL, confidence=0.96),
        )
        fake_extraction = InvoiceExtraction(
            invoice_number={"value": "INV-777", "confidence": 0.95},
            supplier_name={"value": "Acme", "confidence": 0.95},
            total_amount={"value": 450.0, "confidence": 0.95},
        )
        monkeypatch.setattr("services.upload.extract_structured_fields", lambda text, cat: fake_extraction)
        monkeypatch.setattr("api.documents.extract_text", lambda doc_id, storage: "Invoice INV-777 Acme $450.00")
        monkeypatch.setattr("api.documents.extract_structured_fields", lambda text, cat: fake_extraction)

        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setenv("DOCUMENT_STORAGE_DIR", tmp)
            storage = DocumentStorage(base_dir=Path(tmp))
            upload_res = save_upload(
                UploadFile(filename="invoice.pdf", file=io.BytesIO(_make_pdf_bytes())),
                storage,
                {"sub": actors["sub_1"], "organization_id": actors["org_a"], "role": "SUBMITTER"},
                db=db_session,
            )
            doc_id = upload_res["document_id"]

            rev1_hdr = _auth_header(actors["rev_1"], actors["org_a"], "REVIEWER")
            sub1_hdr = _auth_header(actors["sub_1"], actors["org_a"], "SUBMITTER")
            app_hdr = _auth_header(actors["approver"], actors["org_a"], "APPROVER")
            aud_hdr = _auth_header(actors["auditor_a"], actors["org_a"], "AUDITOR")

            # Classification correction
            patch_res = client.patch(
                f"/api/documents/{doc_id}/classification",
                json={"category": "financial", "notes": "Confirmed invoice classification"},
                headers=rev1_hdr,
            )
            assert patch_res.status_code == 200

            # Rule validation
            validate_document(
                document_id=doc_id,
                organization_id=actors["org_a"],
                domain="financial",
                extracted_fields={"invoice_number": "INV-777", "supplier_name": "Acme", "total_amount": "450"},
                db=db_session,
                user_id=actors["rev_1"],
                storage=storage,
            )

            # Submit -> Assign -> Comment -> Request Changes -> Resubmit -> Submit for approval -> Approve
            assert client.post(f"/api/documents/{doc_id}/submit", json={}, headers=sub1_hdr).status_code == 200
            assert client.post(
                f"/api/documents/{doc_id}/assign",
                json={"reviewer_id": actors["rev_1"]},
                headers=rev1_hdr,
            ).status_code == 200
            assert client.post(
                f"/api/documents/{doc_id}/comments",
                json={"comment": "Checking invoice header."},
                headers=rev1_hdr,
            ).status_code == 201
            assert client.post(
                f"/api/documents/{doc_id}/request-changes",
                json={"comment": "Attach signed receipt."},
                headers=rev1_hdr,
            ).status_code == 200
            assert client.post(
                f"/api/documents/{doc_id}/resubmit",
                json={"comment": "Attached signed receipt."},
                headers=sub1_hdr,
            ).status_code == 200
            assert client.post(
                f"/api/documents/{doc_id}/submit-for-approval",
                json={"approver_id": actors["approver"]},
                headers=rev1_hdr,
            ).status_code == 200
            assert client.post(
                f"/api/documents/{doc_id}/approve",
                json={"reason": "Compliant with procurement policy."},
                headers=app_hdr,
            ).status_code == 200

            audit_res = client.get(f"/api/audit/{doc_id}", headers=aud_hdr)
            assert audit_res.status_code == 200
            events = audit_res.json()["events"]
            event_types = [e["event_type"] for e in events]

            expected_prefix = [
                "DOCUMENT_UPLOADED",
                "DOCUMENT_CLASSIFIED",
                "EXTRACTION_COMPLETED",
                "CLASSIFICATION_CORRECTED",
                "EXTRACTION_COMPLETED",
                "DOCUMENT_VALIDATED",
                "DOCUMENT_SUBMITTED",
                "REVIEWER_ASSIGNED",
                "REVIEW_COMMENT_ADDED",
                "CHANGES_REQUESTED",
                "DOCUMENT_RESUBMITTED",
                "SUBMITTED_FOR_APPROVAL",
                "DOCUMENT_APPROVED",
            ]
            assert event_types == expected_prefix

            # Verify user vs system actor identification & strictly non-decreasing chronological sequence
            assert events[0]["actor_type"] == "USER"
            assert events[0]["actor_id"] == actors["sub_1"]
            assert events[1]["actor_type"] == "SYSTEM"
            assert events[1]["actor_id"] == "system"
            seqs = [e["sequence_no"] for e in events]
            assert seqs == sorted(seqs)
            assert len(set(seqs)) == len(seqs)

            # Verify no raw OCR text or extracted values were stored inside audit metadata
            for e in events:
                serialized = json.dumps(e["details"])
                assert "INV-777" not in serialized
                assert "ocr_text" not in e["details"]


class TestAuditImmutabilityScopingAndFailures:
    def test_audit_history_cannot_be_altered_or_deleted_via_api_or_orm(
        self, client: TestClient, db_session: Session
    ) -> None:
        actors = _seed_org_and_users(db_session)
        doc = Document(
            id=f"doc_{uuid.uuid4().hex}",
            organization_id=actors["org_a"],
            uploaded_by=actors["sub_1"],
            filename="contract.pdf",
            file_type="application/pdf",
            file_size=512,
            storage_path="/tmp/contract.pdf",
            status=DocumentStatus.EXTRACTED,
        )
        db_session.add(doc)
        db_session.commit()

        evt = record_audit_event(
            db_session,
            document_id=doc.id,
            organization_id=actors["org_a"],
            event_type="DOCUMENT_UPLOADED",
            actor_id=actors["sub_1"],
            actor_role="SUBMITTER",
            actor_type="USER",
            to_status="UPLOADED",
            commit=True,
        )
        assert evt is not None

        aud_hdr = _auth_header(actors["auditor_a"], actors["org_a"], "AUDITOR")
        # Normal HTTP APIs do not allow altering or deleting audit history
        assert client.put(f"/api/audit/{doc.id}", json={"reason": "tamper"}, headers=aud_hdr).status_code == 405
        assert client.patch(f"/api/audit/{doc.id}", json={"reason": "tamper"}, headers=aud_hdr).status_code == 405
        assert client.delete(f"/api/audit/{doc.id}", headers=aud_hdr).status_code == 405

        # Direct ORM modification and deletion must raise AuditImmutabilityError
        evt.reason = "Tampered reason"
        with pytest.raises(AuditImmutabilityError):
            db_session.flush()
        db_session.rollback()

        fresh_evt = db_session.query(AuditEvent).filter(AuditEvent.id == evt.id).first()
        assert fresh_evt is not None
        assert fresh_evt.reason is None

        db_session.delete(fresh_evt)
        with pytest.raises(AuditImmutabilityError):
            db_session.flush()
        db_session.rollback()

    def test_enforces_organization_and_role_permissions_and_sanitizes_secrets(
        self, client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        actors = _seed_org_and_users(db_session)
        doc = Document(
            id=f"doc_{uuid.uuid4().hex}",
            organization_id=actors["org_a"],
            uploaded_by=actors["sub_1"],
            filename="secret.pdf",
            file_type="application/pdf",
            file_size=512,
            storage_path="/tmp/secret.pdf",
            status=DocumentStatus.IN_REVIEW,
            classification="financial",
            assigned_reviewer_id=actors["rev_1"],
        )
        db_session.add(doc)
        db_session.commit()

        evt = record_audit_event(
            db_session,
            document_id=doc.id,
            organization_id=actors["org_a"],
            event_type="EXTRACTION_FAILED",
            actor_id=actors["rev_1"],
            actor_role="REVIEWER",
            actor_type="USER",
            reason="Failed with Bearer secret-token-value and sk-1234567890abcdef",
            details={
                "password": "my-secret-password",
                "api_key": "sk-secret",
                "ocr_text": "confidential salary data",
                "document_text": "full raw content",
                "extracted_fields": {"ssn": "123-45-6789"},
                "safe_field_count": 3,
                "token_header": "Bearer abcdefghijk",
                "note_summary": "Header was Bearer abcdefghijk",
            },
            commit=True,
        )
        assert evt is not None
        assert evt.reason == "Failed with [REDACTED] and [REDACTED]"
        assert evt.details == {
            "safe_field_count": 3,
            "note_summary": "Header was [REDACTED]",
        }

        # Organization and role scoping checks
        assert client.get(f"/api/audit/{doc.id}").status_code == 401
        assert client.get(
            f"/api/audit/{doc.id}",
            headers=_auth_header(actors["auditor_b"], actors["org_b"], "AUDITOR"),
        ).status_code == 404
        assert client.get(
            f"/api/audit/{doc.id}",
            headers=_auth_header(actors["sub_2"], actors["org_a"], "SUBMITTER"),
        ).status_code == 403
        assert client.get(
            f"/api/audit/{doc.id}",
            headers=_auth_header(actors["rev_2"], actors["org_a"], "REVIEWER"),
        ).status_code == 403
        assert client.get(
            f"/api/audit/{doc.id}",
            headers=_auth_header(actors["sub_1"], actors["org_a"], "SUBMITTER"),
        ).status_code == 200
        assert client.get(
            f"/api/audit/{doc.id}",
            headers=_auth_header(actors["rev_1"], actors["org_a"], "REVIEWER"),
        ).status_code == 200

        # Extraction endpoint failure path records safe EXTRACTION_FAILED event
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setenv("DOCUMENT_STORAGE_DIR", tmp)
            storage = DocumentStorage(base_dir=Path(tmp))
            (storage.base_dir / "metadata").mkdir(parents=True, exist_ok=True)
            (storage.base_dir / "metadata" / f"{doc.id}.json").write_text(
                json.dumps({"document_id": doc.id, "category": "financial"}),
                encoding="utf-8",
            )
            monkeypatch.setattr("api.documents.extract_text", lambda d, s: "text")
            monkeypatch.setattr(
                "api.documents.extract_structured_fields",
                lambda t, c: (_ for _ in ()).throw(RuntimeError("Parser crash")),
            )
            fail_res = client.post(
                f"/api/documents/{doc.id}/extract",
                headers=_auth_header(actors["rev_1"], actors["org_a"], "REVIEWER"),
            )
            assert fail_res.status_code == 422

        audit_rows = (
            db_session.query(AuditEvent)
            .filter(AuditEvent.document_id == doc.id, AuditEvent.event_type == "EXTRACTION_FAILED")
            .all()
        )
        assert len(audit_rows) == 2
        assert audit_rows[1].details["error_type"] == "RuntimeError"
