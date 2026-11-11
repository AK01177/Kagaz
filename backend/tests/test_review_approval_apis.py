"""Tests for permitted review/approval queues, evidence retrieval, comments, decisions, and audit events."""
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
from app.models.policy_validation import PolicyValidationFinding, PolicyValidationRun
from app.models.user import User
from app.models.validation import ValidationResult
from app.models.workflow import AuditEvent, ReviewComment
from main import app

TEST_JWT_SECRET = "test-review-approval-secret-key-at-least-32-bytes"


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


def _seed_actors(db: Session) -> dict[str, str]:
    org_a = str(uuid.uuid4())
    org_b = str(uuid.uuid4())
    submitter = str(uuid.uuid4())
    rev_1 = str(uuid.uuid4())
    rev_2 = str(uuid.uuid4())
    approver_1 = str(uuid.uuid4())
    approver_2 = str(uuid.uuid4())
    admin = str(uuid.uuid4())
    org_b_rev = str(uuid.uuid4())

    db.add_all([
        Organization(id=org_a, name="Acme Corp", slug=f"acme-{org_a[:6]}"),
        Organization(id=org_b, name="Other Corp", slug=f"other-{org_b[:6]}"),
        User(id=submitter, email=f"sub-{submitter[:6]}@acme.test", full_name="Submitter", is_active=True),
        User(id=rev_1, email=f"rev1-{rev_1[:6]}@acme.test", full_name="Reviewer 1", is_active=True),
        User(id=rev_2, email=f"rev2-{rev_2[:6]}@acme.test", full_name="Reviewer 2", is_active=True),
        User(id=approver_1, email=f"app1-{approver_1[:6]}@acme.test", full_name="Approver 1", is_active=True),
        User(id=approver_2, email=f"app2-{approver_2[:6]}@acme.test", full_name="Approver 2", is_active=True),
        User(id=admin, email=f"adm-{admin[:6]}@acme.test", full_name="Admin", is_active=True),
        User(id=org_b_rev, email=f"rev-{org_b_rev[:6]}@other.test", full_name="Other Rev", is_active=True),
    ])
    db.flush()
    db.add_all([
        Membership(organization_id=org_a, user_id=submitter, role=MembershipRole.SUBMITTER, is_active=True),
        Membership(organization_id=org_a, user_id=rev_1, role=MembershipRole.REVIEWER, is_active=True),
        Membership(organization_id=org_a, user_id=rev_2, role=MembershipRole.REVIEWER, is_active=True),
        Membership(organization_id=org_a, user_id=approver_1, role=MembershipRole.APPROVER, is_active=True),
        Membership(organization_id=org_a, user_id=approver_2, role=MembershipRole.APPROVER, is_active=True),
        Membership(organization_id=org_a, user_id=admin, role=MembershipRole.ORG_ADMIN, is_active=True),
        Membership(organization_id=org_b, user_id=org_b_rev, role=MembershipRole.REVIEWER, is_active=True),
    ])
    db.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "submitter": submitter,
        "rev_1": rev_1,
        "rev_2": rev_2,
        "approver_1": approver_1,
        "approver_2": approver_2,
        "admin": admin,
        "org_b_rev": org_b_rev,
    }


def _create_doc(
    db: Session,
    org_id: str,
    uploaded_by: str,
    *,
    filename: str = "invoice.pdf",
    status: DocumentStatus = DocumentStatus.EXTRACTED,
    assigned_reviewer_id: str | None = None,
    assigned_approver_id: str | None = None,
) -> Document:
    doc = Document(
        id=f"doc_{uuid.uuid4().hex}",
        organization_id=org_id,
        uploaded_by=uploaded_by,
        filename=filename,
        file_type="application/pdf",
        file_size=1024,
        storage_path=f"/tmp/{filename}",
        status=status,
        classification="financial",
        classification_confidence=0.94,
        assigned_reviewer_id=assigned_reviewer_id,
        assigned_approver_id=assigned_approver_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


class TestPermittedQueues:
    def test_reviewers_see_only_permitted_documents_in_their_organization(
        self, client: TestClient, db_session: Session
    ) -> None:
        actors = _seed_actors(db_session)

        assigned_to_rev1 = _create_doc(
            db_session,
            actors["org_a"],
            actors["submitter"],
            filename="rev1.pdf",
            status=DocumentStatus.IN_REVIEW,
            assigned_reviewer_id=actors["rev_1"],
        )
        unassigned_submitted = _create_doc(
            db_session,
            actors["org_a"],
            actors["submitter"],
            filename="queue.pdf",
            status=DocumentStatus.SUBMITTED,
        )
        assigned_to_rev2 = _create_doc(
            db_session,
            actors["org_a"],
            actors["submitter"],
            filename="rev2.pdf",
            status=DocumentStatus.IN_REVIEW,
            assigned_reviewer_id=actors["rev_2"],
        )
        already_approved = _create_doc(
            db_session,
            actors["org_a"],
            actors["submitter"],
            filename="done.pdf",
            status=DocumentStatus.APPROVED,
            assigned_reviewer_id=actors["rev_1"],
        )
        other_org_doc = _create_doc(
            db_session,
            actors["org_b"],
            actors["org_b_rev"],
            filename="other_org.pdf",
            status=DocumentStatus.SUBMITTED,
        )

        rev1_hdr = _auth_header(actors["rev_1"], actors["org_a"], "REVIEWER")
        sub_hdr = _auth_header(actors["submitter"], actors["org_a"], "SUBMITTER")
        adm_hdr = _auth_header(actors["admin"], actors["org_a"], "ORG_ADMIN")

        # Submitter cannot access review or approval queues
        assert client.get("/api/documents/workflow/review-queue", headers=sub_hdr).status_code == 403
        assert client.get("/api/documents/workflow/approval-queue", headers=sub_hdr).status_code == 403

        # Reviewer 1 sees own assigned + unassigned submitted in Org A only
        res = client.get("/api/documents/workflow/review-queue", headers=rev1_hdr)
        assert res.status_code == 200
        ids = {item["document_id"] for item in res.json()["items"]}
        assert ids == {assigned_to_rev1.id, unassigned_submitted.id}
        assert assigned_to_rev2.id not in ids
        assert already_approved.id not in ids
        assert other_org_doc.id not in ids

        # assigned_to_me=true excludes unassigned submitted
        res_mine = client.get("/api/documents/workflow/review-queue?assigned_to_me=true", headers=rev1_hdr)
        assert res_mine.status_code == 200
        assert {item["document_id"] for item in res_mine.json()["items"]} == {assigned_to_rev1.id}

        # Org Admin sees all Org A review queue items, never Org B
        res_adm = client.get("/api/documents/workflow/review-queue", headers=adm_hdr)
        assert res_adm.status_code == 200
        assert {item["document_id"] for item in res_adm.json()["items"]} == {
            assigned_to_rev1.id,
            unassigned_submitted.id,
            assigned_to_rev2.id,
        }

    def test_approval_queue_filters_for_permitted_approvers(
        self, client: TestClient, db_session: Session
    ) -> None:
        actors = _seed_actors(db_session)

        for_app1 = _create_doc(
            db_session,
            actors["org_a"],
            actors["submitter"],
            status=DocumentStatus.PENDING_APPROVAL,
            assigned_approver_id=actors["approver_1"],
        )
        unassigned_pending = _create_doc(
            db_session,
            actors["org_a"],
            actors["submitter"],
            status=DocumentStatus.PENDING_APPROVAL,
        )
        for_app2 = _create_doc(
            db_session,
            actors["org_a"],
            actors["submitter"],
            status=DocumentStatus.PENDING_APPROVAL,
            assigned_approver_id=actors["approver_2"],
        )
        other_org_pending = _create_doc(
            db_session,
            actors["org_b"],
            actors["org_b_rev"],
            status=DocumentStatus.PENDING_APPROVAL,
        )

        rev_hdr = _auth_header(actors["rev_1"], actors["org_a"], "REVIEWER")
        app1_hdr = _auth_header(actors["approver_1"], actors["org_a"], "APPROVER")

        assert client.get("/api/documents/workflow/approval-queue", headers=rev_hdr).status_code == 403

        res = client.get("/api/documents/workflow/approval-queue", headers=app1_hdr)
        assert res.status_code == 200
        ids = {item["document_id"] for item in res.json()["items"]}
        assert ids == {for_app1.id, unassigned_pending.id}
        assert for_app2.id not in ids
        assert other_org_pending.id not in ids


class TestReviewEvidenceAndComments:
    def test_retrieve_document_extraction_and_validation_evidence(
        self, client: TestClient, db_session: Session
    ) -> None:
        actors = _seed_actors(db_session)
        doc = _create_doc(
            db_session,
            actors["org_a"],
            actors["submitter"],
            status=DocumentStatus.IN_REVIEW,
            assigned_reviewer_id=actors["rev_1"],
        )
        db_session.add(
            Extraction(document_id=doc.id, field_name="invoice_number", value="INV-900", confidence=0.97)
        )
        db_session.add(
            ValidationResult(
                document_id=doc.id,
                organization_id=actors["org_a"],
                status="REVIEW_REQUIRED",
                policy_version="v2",
                issues=[{"rule": "LIMIT", "severity": "WARNING", "message": "Over threshold"}],
                evidence=[{"source": "expense-policy.pdf", "reference": "Section 4"}],
            )
        )
        run = PolicyValidationRun(
            document_id=doc.id,
            organization_id=actors["org_a"],
            requested_by=actors["rev_1"],
            status="FLAG",
            summary="Requires secondary approval",
            retrieval_outcome="EVIDENCE_FOUND",
            policy_versions=[{"policy_id": "pol_1", "version": "v2"}],
        )
        db_session.add(run)
        db_session.flush()
        db_session.add(
            PolicyValidationFinding(
                run_id=run.id,
                status="FLAG",
                requirement="Clause 4.2: Invoices above $500 require secondary approval.",
                explanation="Amount exceeds single-signer limit.",
                field_name="total_amount",
                document_value="650.00",
                confidence=0.89,
                source_references=[{"document": "expense-policy.pdf", "quote": "Above $500 requires approval."}],
            )
        )
        db_session.commit()

        rev1_hdr = _auth_header(actors["rev_1"], actors["org_a"], "REVIEWER")
        rev2_hdr = _auth_header(actors["rev_2"], actors["org_a"], "REVIEWER")
        other_org_hdr = _auth_header(actors["org_b_rev"], actors["org_b"], "REVIEWER")

        # Another assigned-blocked reviewer and cross-org user are rejected
        assert client.get(f"/api/documents/{doc.id}/review", headers=rev2_hdr).status_code == 403
        assert client.get(f"/api/documents/{doc.id}/review", headers=other_org_hdr).status_code == 404

        res = client.get(f"/api/documents/{doc.id}/review", headers=rev1_hdr)
        assert res.status_code == 200
        body = res.json()
        assert body["document"]["document_id"] == doc.id
        assert body["extractions"][0]["field_name"] == "invoice_number"
        assert body["extractions"][0]["value"] == "INV-900"
        assert body["validation"]["status"] == "REVIEW_REQUIRED"
        assert body["policy_validation_runs"][0]["findings"][0]["status"] == "FLAG"
        assert body["policy_validation_runs"][0]["findings"][0]["requirement"].startswith("Clause 4.2")

    def test_submit_review_comment_persists_comment_and_audit_event(
        self, client: TestClient, db_session: Session
    ) -> None:
        actors = _seed_actors(db_session)
        doc = _create_doc(
            db_session,
            actors["org_a"],
            actors["submitter"],
            status=DocumentStatus.IN_REVIEW,
            assigned_reviewer_id=actors["rev_1"],
        )
        rev1_hdr = _auth_header(actors["rev_1"], actors["org_a"], "REVIEWER")
        rev2_hdr = _auth_header(actors["rev_2"], actors["org_a"], "REVIEWER")
        sub_hdr = _auth_header(actors["submitter"], actors["org_a"], "SUBMITTER")

        # Empty / unauthorized comments rejected
        assert client.post(f"/api/documents/{doc.id}/comments", json={"comment": "   "}, headers=rev1_hdr).status_code == 422
        assert client.post(f"/api/documents/{doc.id}/comments", json={"comment": "Note"}, headers=sub_hdr).status_code == 403
        assert client.post(f"/api/documents/{doc.id}/comments", json={"comment": "Note"}, headers=rev2_hdr).status_code == 403

        # Valid comment persists and generates audit event
        res = client.post(
            f"/api/documents/{doc.id}/comments",
            json={"comment": "Verified vendor address against PO."},
            headers=rev1_hdr,
        )
        assert res.status_code == 201
        comment_body = res.json()
        assert comment_body["author_id"] == actors["rev_1"]
        assert comment_body["comment"] == "Verified vendor address against PO."

        review_detail = client.get(f"/api/documents/{doc.id}/review", headers=rev1_hdr).json()
        assert len(review_detail["comments"]) == 1
        assert review_detail["audit_events"][0]["event_type"] == "REVIEW_COMMENT_ADDED"
        assert review_detail["audit_events"][0]["reason"] == "Verified vendor address against PO."


class TestFinalDecisionsAndAuditEvents:
    def test_decision_records_actor_timestamp_reason_and_creates_audit_event(
        self, client: TestClient, db_session: Session
    ) -> None:
        actors = _seed_actors(db_session)
        doc = _create_doc(
            db_session,
            actors["org_a"],
            actors["submitter"],
            status=DocumentStatus.PENDING_APPROVAL,
            assigned_reviewer_id=actors["rev_1"],
            assigned_approver_id=actors["approver_1"],
        )
        app1_hdr = _auth_header(actors["approver_1"], actors["org_a"], "APPROVER")
        app2_hdr = _auth_header(actors["approver_2"], actors["org_a"], "APPROVER")
        rev1_hdr = _auth_header(actors["rev_1"], actors["org_a"], "REVIEWER")

        # Wrong approver & reviewer rejected
        assert client.post(f"/api/documents/{doc.id}/approve", json={"reason": "No"}, headers=app2_hdr).status_code == 403
        assert client.post(f"/api/documents/{doc.id}/reject", json={"reason": "No"}, headers=rev1_hdr).status_code == 403

        # Eligible approver approves with reason
        res = client.post(
            f"/api/documents/{doc.id}/approve",
            json={"reason": "Matches approved budget PO-442."},
            headers=app1_hdr,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "APPROVED"
        assert body["decision"] == "APPROVED"
        assert body["last_decision_by"] == actors["approver_1"]
        assert body["last_decision_at"] is not None
        assert body["last_decision_comment"] == "Matches approved budget PO-442."
        assert body["audit_event"]["event_type"] == "DOCUMENT_APPROVED"
        assert body["audit_event"]["actor_id"] == actors["approver_1"]
        assert body["audit_event"]["decision"] == "APPROVED"
        assert body["audit_event"]["reason"] == "Matches approved budget PO-442."
        assert body["audit_event"]["created_at"] is not None

        # Duplicate decision (re-approve or reject) is rejected without extra audit event
        dup_approve = client.post(
            f"/api/documents/{doc.id}/approve",
            json={"reason": "Clicking again"},
            headers=app1_hdr,
        )
        assert dup_approve.status_code == 409
        assert dup_approve.json()["error"]["code"] == "INVALID_STATE_TRANSITION"
        assert dup_approve.json()["error"]["details"]["duplicate_decision"] is True

        dup_reject = client.post(
            f"/api/documents/{doc.id}/reject",
            json={"reason": "Trying to reverse"},
            headers=app1_hdr,
        )
        assert dup_reject.status_code == 409
        assert dup_reject.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

        # Audit trail endpoint returns exact single approval audit event
        audit_res = client.get(f"/api/audit/{doc.id}", headers=app1_hdr)
        assert audit_res.status_code == 200
        events = audit_res.json()["events"]
        assert len(events) == 1
        assert events[0]["event_type"] == "DOCUMENT_APPROVED"

    def test_request_changes_and_reject_record_audit_events_and_reject_ineligible_docs(
        self, client: TestClient, db_session: Session
    ) -> None:
        actors = _seed_actors(db_session)
        rev1_hdr = _auth_header(actors["rev_1"], actors["org_a"], "REVIEWER")
        app1_hdr = _auth_header(actors["approver_1"], actors["org_a"], "APPROVER")

        # Approver cannot decide on ineligible states (CLASSIFIED, SUBMITTED, CHANGES_REQUESTED)
        for bad_status in (
            DocumentStatus.CLASSIFIED,
            DocumentStatus.SUBMITTED,
            DocumentStatus.CHANGES_REQUESTED,
        ):
            ineligible = _create_doc(db_session, actors["org_a"], actors["submitter"], status=bad_status)
            r = client.post(f"/api/documents/{ineligible.id}/reject", json={"reason": "Invalid"}, headers=app1_hdr)
            assert r.status_code == 409
            assert r.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

        # Reviewer requests changes with comment -> creates CHANGES_REQUESTED audit event
        doc = _create_doc(
            db_session,
            actors["org_a"],
            actors["submitter"],
            status=DocumentStatus.IN_REVIEW,
            assigned_reviewer_id=actors["rev_1"],
        )
        req_changes = client.post(
            f"/api/documents/{doc.id}/request-changes",
            json={"comment": "Line item totals do not sum correctly."},
            headers=rev1_hdr,
        )
        assert req_changes.status_code == 200
        assert req_changes.json()["status"] == "CHANGES_REQUESTED"
        assert req_changes.json()["audit_event"]["event_type"] == "CHANGES_REQUESTED"
        assert req_changes.json()["audit_event"]["decision"] == "CHANGES_REQUESTED"

        # Separate IN_REVIEW document rejected by approver with reason -> creates DOCUMENT_REJECTED audit event
        doc_reject = _create_doc(
            db_session,
            actors["org_a"],
            actors["submitter"],
            status=DocumentStatus.IN_REVIEW,
            assigned_reviewer_id=actors["rev_1"],
        )
        rej_res = client.post(
            f"/api/documents/{doc_reject.id}/reject",
            json={"reason": "Duplicate invoice number submitted."},
            headers=app1_hdr,
        )
        assert rej_res.status_code == 200
        rej_body = rej_res.json()
        assert rej_body["status"] == "REJECTED"
        assert rej_body["decision"] == "REJECTED"
        assert rej_body["last_decision_by"] == actors["approver_1"]
        assert rej_body["last_decision_at"] is not None
        assert rej_body["last_decision_comment"] == "Duplicate invoice number submitted."
        assert rej_body["audit_event"]["event_type"] == "DOCUMENT_REJECTED"

        audit_rows = db_session.query(AuditEvent).filter(AuditEvent.document_id == doc_reject.id).all()
        assert len(audit_rows) == 1
        assert audit_rows[0].decision == "REJECTED"
        assert audit_rows[0].reason == "Duplicate invoice number submitted."
