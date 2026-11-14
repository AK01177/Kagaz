"""Unit and integration tests for backend-enforced document workflow state machine."""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import create_access_token
from app.db.session import get_db
from app.db.base import Base
from app.models.document import Document, DocumentStatus
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.policy_validation import PolicyValidationRun
from app.models.user import User
from app.models.validation import ValidationResult
from app.models.workflow import DocumentTransition, WorkflowAction
from main import app
from services.validation import validate_document
from services.workflow import WorkflowError, assign_reviewer, submit_document
from storage.document_storage import DocumentStorage

TEST_JWT_SECRET = "test-workflow-secret-key-at-least-32-bytes"


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


def _seed_org_actors(db: Session) -> dict[str, str]:
    org_a_id = str(uuid.uuid4())
    org_b_id = str(uuid.uuid4())
    submitter_id = str(uuid.uuid4())
    reviewer_1_id = str(uuid.uuid4())
    reviewer_2_id = str(uuid.uuid4())
    approver_id = str(uuid.uuid4())
    inactive_reviewer_id = str(uuid.uuid4())
    other_org_reviewer_id = str(uuid.uuid4())
    admin_id = str(uuid.uuid4())

    db.add_all([
        Organization(id=org_a_id, name="Acme Corp", slug=f"acme-{org_a_id[:8]}"),
        Organization(id=org_b_id, name="Beta Corp", slug=f"beta-{org_b_id[:8]}"),
        User(id=submitter_id, email=f"sub-{submitter_id[:6]}@acme.test", full_name="Sub One", is_active=True),
        User(id=reviewer_1_id, email=f"rev1-{reviewer_1_id[:6]}@acme.test", full_name="Rev One", is_active=True),
        User(id=reviewer_2_id, email=f"rev2-{reviewer_2_id[:6]}@acme.test", full_name="Rev Two", is_active=True),
        User(id=approver_id, email=f"app-{approver_id[:6]}@acme.test", full_name="App One", is_active=True),
        User(id=inactive_reviewer_id, email=f"inact-{inactive_reviewer_id[:6]}@acme.test", full_name="Inactive Rev", is_active=False),
        User(id=other_org_reviewer_id, email=f"other-{other_org_reviewer_id[:6]}@beta.test", full_name="Beta Rev", is_active=True),
        User(id=admin_id, email=f"adm-{admin_id[:6]}@acme.test", full_name="Admin One", is_active=True),
    ])
    db.flush()
    db.add_all([
        Membership(organization_id=org_a_id, user_id=submitter_id, role=MembershipRole.SUBMITTER, is_active=True),
        Membership(organization_id=org_a_id, user_id=reviewer_1_id, role=MembershipRole.REVIEWER, is_active=True),
        Membership(organization_id=org_a_id, user_id=reviewer_2_id, role=MembershipRole.REVIEWER, is_active=True),
        Membership(organization_id=org_a_id, user_id=approver_id, role=MembershipRole.APPROVER, is_active=True),
        Membership(organization_id=org_a_id, user_id=inactive_reviewer_id, role=MembershipRole.REVIEWER, is_active=True),
        Membership(organization_id=org_b_id, user_id=other_org_reviewer_id, role=MembershipRole.REVIEWER, is_active=True),
        Membership(organization_id=org_a_id, user_id=admin_id, role=MembershipRole.ORG_ADMIN, is_active=True),
    ])
    db.commit()

    return {
        "org_a": org_a_id,
        "org_b": org_b_id,
        "submitter": submitter_id,
        "reviewer_1": reviewer_1_id,
        "reviewer_2": reviewer_2_id,
        "approver": approver_id,
        "inactive_reviewer": inactive_reviewer_id,
        "other_org_reviewer": other_org_reviewer_id,
        "admin": admin_id,
    }


def _seed_document(
    db: Session,
    org_id: str,
    uploaded_by: str,
    status: DocumentStatus = DocumentStatus.EXTRACTED,
) -> Document:
    doc = Document(
        id=f"doc_{uuid.uuid4().hex}",
        organization_id=org_id,
        uploaded_by=uploaded_by,
        filename="invoice.pdf",
        file_type="application/pdf",
        file_size=2048,
        storage_path="/tmp/invoice.pdf",
        status=status,
        classification="financial",
        classification_confidence=0.95,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


class TestWorkflowHappyPathAndHistory:
    def test_submit_assign_request_changes_resubmit_approve_preserves_history(
        self, client: TestClient, db_session: Session
    ) -> None:
        actors = _seed_org_actors(db_session)
        doc = _seed_document(db_session, actors["org_a"], actors["submitter"], DocumentStatus.EXTRACTED)

        sub_hdr = _auth_header(actors["submitter"], actors["org_a"], "SUBMITTER")
        rev1_hdr = _auth_header(actors["reviewer_1"], actors["org_a"], "REVIEWER")
        rev2_hdr = _auth_header(actors["reviewer_2"], actors["org_a"], "REVIEWER")
        app_hdr = _auth_header(actors["approver"], actors["org_a"], "APPROVER")
        adm_hdr = _auth_header(actors["admin"], actors["org_a"], "ORG_ADMIN")

        # 1. Submit completed document to queue
        res = client.post(f"/api/documents/{doc.id}/submit", json={"comment": "Initial submit"}, headers=sub_hdr)
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "SUBMITTED"
        assert body["revision_number"] == 1
        assert body["assigned_reviewer_id"] is None

        # 2. Assign to eligible reviewer -> IN_REVIEW
        res = client.post(
            f"/api/documents/{doc.id}/assign",
            json={"reviewer_id": actors["reviewer_1"], "comment": "Routing to primary reviewer"},
            headers=adm_hdr,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "IN_REVIEW"
        assert body["assigned_reviewer_id"] == actors["reviewer_1"]

        # 3. Assigned reviewer requests changes -> CHANGES_REQUESTED
        res = client.post(
            f"/api/documents/{doc.id}/request-changes",
            json={"comment": "Vendor tax ID is missing on page 2."},
            headers=rev1_hdr,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "CHANGES_REQUESTED"
        assert body["last_decision_by"] == actors["reviewer_1"]
        assert body["last_decision_comment"] == "Vendor tax ID is missing on page 2."

        # 4. Submitter resubmits -> returns to IN_REVIEW with revision incremented and history preserved
        res = client.post(
            f"/api/documents/{doc.id}/resubmit",
            json={"comment": "Uploaded corrected invoice with tax ID."},
            headers=sub_hdr,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "IN_REVIEW"
        assert body["revision_number"] == 2
        assert body["assigned_reviewer_id"] == actors["reviewer_1"]

        # 5. Reassign to second reviewer -> IN_REVIEW
        res = client.post(
            f"/api/documents/{doc.id}/assign",
            json={"reviewer_id": actors["reviewer_2"], "comment": "Handing over to Rev 2"},
            headers=rev1_hdr,
        )
        assert res.status_code == 200
        assert res.json()["assigned_reviewer_id"] == actors["reviewer_2"]

        # 6. Reviewer 2 forwards for approval -> PENDING_APPROVAL
        res = client.post(
            f"/api/documents/{doc.id}/submit-for-approval",
            json={"approver_id": actors["approver"], "comment": "Fields verified"},
            headers=rev2_hdr,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "PENDING_APPROVAL"
        assert body["assigned_approver_id"] == actors["approver"]

        # 7. Approver approves -> APPROVED
        res = client.post(
            f"/api/documents/{doc.id}/approve",
            json={"comment": "Approved after tax verification."},
            headers=app_hdr,
        )
        assert res.status_code == 200
        final = res.json()
        assert final["status"] == "APPROVED"
        assert final["last_decision_by"] == actors["approver"]
        assert final["last_decision_comment"] == "Approved after tax verification."

        actions = [entry["action"] for entry in final["history"]]
        assert actions == [
            "SUBMIT",
            "ASSIGN_REVIEWER",
            "REQUEST_CHANGES",
            "RESUBMIT",
            "REASSIGN_REVIEWER",
            "SUBMIT_FOR_APPROVAL",
            "APPROVE",
        ]
        assert final["history"][2]["comment"] == "Vendor tax ID is missing on page 2."
        assert final["history"][3]["revision_number"] == 2
        assert final["history"][4]["previous_assignee_id"] == actors["reviewer_1"]
        assert final["history"][4]["assigned_to_id"] == actors["reviewer_2"]

    def test_auto_route_picks_eligible_reviewer(self, client: TestClient, db_session: Session) -> None:
        actors = _seed_org_actors(db_session)
        doc = _seed_document(db_session, actors["org_a"], actors["submitter"], DocumentStatus.CLASSIFIED)
        sub_hdr = _auth_header(actors["submitter"], actors["org_a"], "SUBMITTER")

        res = client.post(f"/api/documents/{doc.id}/submit", json={"auto_route": True}, headers=sub_hdr)
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "IN_REVIEW"
        assert body["assigned_reviewer_id"] in {actors["reviewer_1"], actors["reviewer_2"]}

        list_res = client.get("/api/documents/workflow/reviewers", headers=sub_hdr)
        assert list_res.status_code == 200
        listed_ids = {item["user_id"] for item in list_res.json()}
        assert actors["reviewer_1"] in listed_ids
        assert actors["inactive_reviewer"] not in listed_ids
        assert actors["other_org_reviewer"] not in listed_ids
        assert actors["submitter"] not in listed_ids


class TestEligibilityValidationAndErrors:
    def test_rejects_ineligible_reviewers(self, client: TestClient, db_session: Session) -> None:
        actors = _seed_org_actors(db_session)
        doc = _seed_document(db_session, actors["org_a"], actors["submitter"], DocumentStatus.EXTRACTED)
        sub_hdr = _auth_header(actors["submitter"], actors["org_a"], "SUBMITTER")
        adm_hdr = _auth_header(actors["admin"], actors["org_a"], "ORG_ADMIN")

        assert client.post(f"/api/documents/{doc.id}/submit", json={}, headers=sub_hdr).status_code == 200

        for invalid_target in (
            actors["submitter"],           # SUBMITTER role cannot review
            actors["approver"],            # APPROVER is not an eligible REVIEWER
            actors["inactive_reviewer"],   # inactive User
            actors["other_org_reviewer"],  # wrong organization
            str(uuid.uuid4()),             # non-existent user
        ):
            res = client.post(
                f"/api/documents/{doc.id}/assign",
                json={"reviewer_id": invalid_target},
                headers=adm_hdr,
            )
            assert res.status_code == 422
            assert res.json()["error"]["code"] == "INELIGIBLE_REVIEWER"

    def test_request_changes_requires_non_empty_comment(
        self, client: TestClient, db_session: Session
    ) -> None:
        actors = _seed_org_actors(db_session)
        doc = _seed_document(db_session, actors["org_a"], actors["submitter"], DocumentStatus.EXTRACTED)
        sub_hdr = _auth_header(actors["submitter"], actors["org_a"], "SUBMITTER")
        rev_hdr = _auth_header(actors["reviewer_1"], actors["org_a"], "REVIEWER")

        client.post(
            f"/api/documents/{doc.id}/submit",
            json={"reviewer_id": actors["reviewer_1"]},
            headers=sub_hdr,
        )

        for payload in (None, {}, {"comment": ""}, {"comment": "   \t\n "}):
            res = client.post(
                f"/api/documents/{doc.id}/request-changes",
                json=payload,
                headers=rev_hdr,
            )
            assert res.status_code == 422
            assert res.json()["error"]["code"] == "COMMENT_REQUIRED"

        db_session.refresh(doc)
        assert doc.status == DocumentStatus.IN_REVIEW

    def test_invalid_transitions_return_consistent_errors(
        self, client: TestClient, db_session: Session
    ) -> None:
        actors = _seed_org_actors(db_session)
        rev_hdr = _auth_header(actors["reviewer_1"], actors["org_a"], "REVIEWER")
        app_hdr = _auth_header(actors["approver"], actors["org_a"], "APPROVER")
        sub_hdr = _auth_header(actors["submitter"], actors["org_a"], "SUBMITTER")

        # Cannot submit unfinished UPLOADED or FAILED documents
        uploaded_doc = _seed_document(db_session, actors["org_a"], actors["submitter"], DocumentStatus.UPLOADED)
        res = client.post(f"/api/documents/{uploaded_doc.id}/submit", json={}, headers=sub_hdr)
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

        # Cannot approve unsubmitted or SUBMITTED documents
        extracted_doc = _seed_document(db_session, actors["org_a"], actors["submitter"], DocumentStatus.EXTRACTED)
        res = client.post(f"/api/documents/{extracted_doc.id}/approve", json={}, headers=app_hdr)
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

        # Cannot resubmit a document that is not in CHANGES_REQUESTED
        res = client.post(f"/api/documents/{extracted_doc.id}/resubmit", json={}, headers=sub_hdr)
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

        # Terminal REJECTED document cannot be approved, assigned, or resubmitted
        rejected_doc = _seed_document(db_session, actors["org_a"], actors["submitter"], DocumentStatus.REJECTED)
        for path, hdr, body in (
            (f"/api/documents/{rejected_doc.id}/approve", app_hdr, {}),
            (f"/api/documents/{rejected_doc.id}/assign", rev_hdr, {"reviewer_id": actors["reviewer_1"]}),
            (f"/api/documents/{rejected_doc.id}/resubmit", sub_hdr, {}),
            (f"/api/documents/{rejected_doc.id}/request-changes", rev_hdr, {"comment": "Too late"}),
        ):
            r = client.post(path, json=body, headers=hdr)
            assert r.status_code == 409
            assert r.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


class TestAuthorizationAndIsolation:
    def test_enforces_roles_assignee_ownership_and_tenant_isolation(
        self, client: TestClient, db_session: Session
    ) -> None:
        actors = _seed_org_actors(db_session)
        doc = _seed_document(db_session, actors["org_a"], actors["submitter"], DocumentStatus.EXTRACTED)
        sub_hdr = _auth_header(actors["submitter"], actors["org_a"], "SUBMITTER")
        rev1_hdr = _auth_header(actors["reviewer_1"], actors["org_a"], "REVIEWER")
        rev2_hdr = _auth_header(actors["reviewer_2"], actors["org_a"], "REVIEWER")
        other_org_hdr = _auth_header(actors["other_org_reviewer"], actors["org_b"], "REVIEWER")

        # Unauthenticated request rejected
        assert client.post(f"/api/documents/{doc.id}/submit", json={}).status_code == 401

        # Reviewer cannot submit
        r = client.post(f"/api/documents/{doc.id}/submit", json={}, headers=rev1_hdr)
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "WORKFLOW_SUBMIT_FORBIDDEN"

        # Submitter submits to rev1
        assert client.post(
            f"/api/documents/{doc.id}/submit",
            json={"reviewer_id": actors["reviewer_1"]},
            headers=sub_hdr,
        ).status_code == 200

        # Submitter cannot assign or approve
        assert client.post(
            f"/api/documents/{doc.id}/assign",
            json={"reviewer_id": actors["reviewer_2"]},
            headers=sub_hdr,
        ).status_code == 403
        assert client.post(f"/api/documents/{doc.id}/approve", json={}, headers=sub_hdr).status_code == 403

        # Reviewer cannot approve/reject
        assert client.post(f"/api/documents/{doc.id}/approve", json={}, headers=rev1_hdr).status_code == 403
        assert client.post(f"/api/documents/{doc.id}/reject", json={}, headers=rev1_hdr).status_code == 403

        # Another unassigned reviewer cannot request changes while assigned to rev1
        r = client.post(
            f"/api/documents/{doc.id}/request-changes",
            json={"comment": "Unauthorized hijack"},
            headers=rev2_hdr,
        )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "WORKFLOW_FORBIDDEN"

        # Cross-organization user cannot view or mutate the document
        r = client.get(f"/api/documents/{doc.id}/workflow", headers=other_org_hdr)
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


class TestValidationSeparationAndAtomicity:
    def test_ai_findings_remain_separate_from_workflow_decisions(
        self, client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        actors = _seed_org_actors(db_session)
        doc = _seed_document(db_session, actors["org_a"], actors["submitter"], DocumentStatus.EXTRACTED)
        sub_hdr = _auth_header(actors["submitter"], actors["org_a"], "SUBMITTER")
        rev1_hdr = _auth_header(actors["reviewer_1"], actors["org_a"], "REVIEWER")
        app_hdr = _auth_header(actors["approver"], actors["org_a"], "APPROVER")

        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setenv("DOCUMENT_STORAGE_DIR", tmp)
            storage = DocumentStorage(base_dir=Path(tmp))
            meta_dir = storage.base_dir / "metadata"
            meta_dir.mkdir(parents=True, exist_ok=True)
            meta_file = meta_dir / f"{doc.id}.json"
            meta_file.write_text(
                json.dumps({"document_id": doc.id, "organization_id": actors["org_a"], "status": "EXTRACTED"}),
                encoding="utf-8",
            )

            # Failing validation result must NOT auto-reject document
            fail_res = validate_document(
                document_id=doc.id,
                organization_id=actors["org_a"],
                domain="financial",
                extracted_fields={},
                db=db_session,
                storage=storage,
            )
            assert fail_res["status"] == "FAIL"
            db_session.refresh(doc)
            assert doc.status == DocumentStatus.EXTRACTED

            # Move document into review and run PASS validation + FAIL PolicyValidationRun
            client.post(
                f"/api/documents/{doc.id}/submit",
                json={"reviewer_id": actors["reviewer_1"]},
                headers=sub_hdr,
            )
            pass_res = validate_document(
                document_id=doc.id,
                organization_id=actors["org_a"],
                domain="financial",
                extracted_fields={"invoice_number": "INV-1", "supplier_name": "Acme", "total_amount": "100"},
                db=db_session,
                storage=storage,
            )
            assert pass_res["status"] == "PASS"
            db_session.add(
                PolicyValidationRun(
                    document_id=doc.id,
                    organization_id=actors["org_a"],
                    requested_by=actors["reviewer_1"],
                    status="FAIL",
                    summary="Advisory policy check flagged expense threshold.",
                    retrieval_outcome="EVIDENCE_FOUND",
                )
            )
            db_session.commit()

            db_session.refresh(doc)
            # Neither PASS nor FAIL AI validation auto-approves or auto-rejects IN_REVIEW document
            assert doc.status == DocumentStatus.IN_REVIEW
            sidecar = json.loads(meta_file.read_text(encoding="utf-8"))
            assert sidecar["status"] == "IN_REVIEW"

            wf = client.get(f"/api/documents/{doc.id}/workflow", headers=rev1_hdr).json()
            assert wf["status"] == "IN_REVIEW"
            assert wf["validation_summary"]["status"] == "PASS"
            assert wf["validation_summary"]["latest_policy_run_status"] == "FAIL"

            # Explicit human decision still works regardless of advisory AI status
            reject_res = client.post(
                f"/api/documents/{doc.id}/reject",
                json={"comment": "Policy run failed manual inspection."},
                headers=app_hdr,
            )
            assert reject_res.status_code == 200
            assert reject_res.json()["status"] == "REJECTED"

    def test_state_and_history_persist_atomically_with_rollback_on_failure(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        actors = _seed_org_actors(db_session)
        doc = _seed_document(db_session, actors["org_a"], actors["submitter"], DocumentStatus.EXTRACTED)

        def _fail_flush(*_args, **_kwargs):
            raise RuntimeError("Simulated DB flush failure")

        monkeypatch.setattr(db_session, "flush", _fail_flush)

        with pytest.raises(RuntimeError, match="Simulated DB flush failure"):
            submit_document(
                db_session,
                doc.id,
                {"sub": actors["submitter"], "organization_id": actors["org_a"], "role": "SUBMITTER", "active": True},
                reviewer_id=actors["reviewer_1"],
            )

        monkeypatch.undo()
        db_session.expire_all()
        fresh_doc = db_session.query(Document).filter(Document.id == doc.id).first()
        transitions = db_session.query(DocumentTransition).filter(DocumentTransition.document_id == doc.id).all()
        assert fresh_doc is not None
        assert fresh_doc.status == DocumentStatus.EXTRACTED
        assert fresh_doc.assigned_reviewer_id is None
        assert fresh_doc.revision_number == 0
        assert transitions == []
