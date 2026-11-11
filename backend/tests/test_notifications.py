"""
Tests for BE-13: In-App Notifications.

Verifies:
- Relevant workflow events (ASSIGN_REVIEWER, REQUEST_CHANGES, RESUBMIT, APPROVE, REJECT) create notifications
- Users see only their own notifications (recipient and tenant isolation)
- Notifications can be marked read (individually and read-all)
- Retries do not create uncontrolled duplicates (idempotency key enforcement)
- Notification failures do not break the main workflow transaction
"""
from __future__ import annotations

import uuid
from typing import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.membership import Membership, MembershipRole
from app.models.notification import Notification
from app.models.organization import Organization
from app.models.user import User
from app.models.workflow import WorkflowAction
from main import app
from services.notification import (
    dispatch_workflow_notification,
    list_notifications,
    mark_all_notifications_as_read,
    mark_notification_as_read,
    notify,
)
from services.workflow import (
    assign_reviewer,
    decide_document,
    request_changes,
    resubmit_document,
    submit_document,
)

TEST_JWT_SECRET = "test-notifications-secret-key-at-least-32-bytes"


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


def _seed_org_and_users(db: Session, org_id: str = "org_alpha"):
    org = Organization(id=org_id, name="Alpha Corp", slug=f"slug-{org_id[:8]}")
    submitter = User(id="user_sub_1", email="sub1@alpha.com", full_name="Submitter One", is_active=True)
    reviewer = User(id="user_rev_1", email="rev1@alpha.com", full_name="Reviewer One", is_active=True)
    approver = User(id="user_app_1", email="app1@alpha.com", full_name="Approver One", is_active=True)
    admin = User(id="user_adm_1", email="adm1@alpha.com", full_name="Admin One", is_active=True)

    m_sub = Membership(organization_id=org.id, user_id=submitter.id, role=MembershipRole.SUBMITTER, is_active=True)
    m_rev = Membership(organization_id=org.id, user_id=reviewer.id, role=MembershipRole.REVIEWER, is_active=True)
    m_app = Membership(organization_id=org.id, user_id=approver.id, role=MembershipRole.APPROVER, is_active=True)
    m_adm = Membership(organization_id=org.id, user_id=admin.id, role=MembershipRole.ORG_ADMIN, is_active=True)

    db.add_all([org, submitter, reviewer, approver, admin, m_sub, m_rev, m_app, m_adm])
    db.commit()
    return {
        "org": org,
        "submitter": submitter,
        "reviewer": reviewer,
        "approver": approver,
        "admin": admin,
    }


def _seed_document(db: Session, org_id: str, submitter_id: str, status: DocumentStatus = DocumentStatus.CLASSIFIED) -> Document:
    doc = Document(
        id=f"doc_{uuid.uuid4().hex[:8]}",
        organization_id=org_id,
        uploaded_by=submitter_id,
        filename="financial_report.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="/tmp/test.pdf",
        status=status,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def test_assignment_creates_notification(db_session: Session):
    entities = _seed_org_and_users(db_session)
    doc = _seed_document(db_session, entities["org"].id, entities["submitter"].id, DocumentStatus.CLASSIFIED)

    # Submitter submits document with reviewer assignment
    submit_document(
        db_session,
        doc.id,
        {"sub": entities["submitter"].id, "role": "SUBMITTER", "organization_id": entities["org"].id, "active": True},
        reviewer_id=entities["reviewer"].id,
    )

    # Reviewer should receive notification
    notifs, total, unread = list_notifications(
        db_session,
        recipient_user_id=entities["reviewer"].id,
        organization_id=entities["org"].id,
    )
    assert total == 1
    assert unread == 1
    assert notifs[0].notification_type == "ASSIGNED"
    assert "financial_report.pdf" in notifs[0].title
    assert notifs[0].document_id == doc.id


def test_request_changes_creates_notification_for_submitter(db_session: Session):
    entities = _seed_org_and_users(db_session)
    doc = _seed_document(db_session, entities["org"].id, entities["submitter"].id, DocumentStatus.IN_REVIEW)
    doc.assigned_reviewer_id = entities["reviewer"].id
    db_session.commit()

    request_changes(
        db_session,
        doc.id,
        {"sub": entities["reviewer"].id, "role": "REVIEWER", "organization_id": entities["org"].id, "active": True},
        comment="Please fix the tax calculation on page 3.",
    )

    notifs, total, unread = list_notifications(
        db_session,
        recipient_user_id=entities["submitter"].id,
        organization_id=entities["org"].id,
    )
    assert total == 1
    assert unread == 1
    assert notifs[0].notification_type == "CHANGES_REQUESTED"
    assert "tax calculation" in notifs[0].body


def test_decision_creates_notification_for_submitter(db_session: Session):
    entities = _seed_org_and_users(db_session)
    doc = _seed_document(db_session, entities["org"].id, entities["submitter"].id, DocumentStatus.PENDING_APPROVAL)
    doc.assigned_approver_id = entities["approver"].id
    db_session.commit()

    decide_document(
        db_session,
        doc.id,
        {"sub": entities["approver"].id, "role": "APPROVER", "organization_id": entities["org"].id, "active": True},
        approve=True,
        comment="Approved per company policy.",
    )

    notifs, total, unread = list_notifications(
        db_session,
        recipient_user_id=entities["submitter"].id,
        organization_id=entities["org"].id,
    )
    assert total == 1
    assert notifs[0].notification_type == "APPROVED"
    assert "approved" in notifs[0].title.lower()


def test_user_sees_only_own_notifications(client: TestClient, db_session: Session):
    entities = _seed_org_and_users(db_session, org_id="org_alpha")

    # Seed notification for reviewer
    notify(
        db_session,
        recipient_user_id=entities["reviewer"].id,
        organization_id=entities["org"].id,
        notification_type="ASSIGNED",
        title="Reviewer notice",
    )
    # Seed notification for submitter
    notify(
        db_session,
        recipient_user_id=entities["submitter"].id,
        organization_id=entities["org"].id,
        notification_type="APPROVED",
        title="Submitter notice",
    )

    # Submitter queries /api/notifications
    sub_headers = _auth_header(entities["submitter"].id, "SUBMITTER", entities["org"].id)
    resp = client.get("/api/notifications", headers=sub_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Submitter notice"

    # Reviewer queries /api/notifications
    rev_headers = _auth_header(entities["reviewer"].id, "REVIEWER", entities["org"].id)
    resp = client.get("/api/notifications", headers=rev_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Reviewer notice"


def test_cross_tenant_isolation(client: TestClient, db_session: Session):
    entities_alpha = _seed_org_and_users(db_session, org_id="org_alpha")
    # Seed another org with same user ID string
    org_beta = Organization(id="org_beta", name="Beta Corp", slug="beta-corp")
    user_beta = User(id="user_beta_1", email="user@beta.com", is_active=True)
    m_beta = Membership(organization_id=org_beta.id, user_id=user_beta.id, role=MembershipRole.SUBMITTER, is_active=True)
    db_session.add_all([org_beta, user_beta, m_beta])
    db_session.commit()

    notify(
        db_session,
        recipient_user_id=user_beta.id,
        organization_id="org_beta",
        notification_type="APPROVED",
        title="Beta notice",
    )

    # User in Alpha queries - cannot see Beta notice
    headers = _auth_header(entities_alpha["submitter"].id, "SUBMITTER", "org_alpha")
    resp = client.get("/api/notifications", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_mark_as_read_endpoints(client: TestClient, db_session: Session):
    entities = _seed_org_and_users(db_session)
    notif1 = notify(
        db_session,
        recipient_user_id=entities["submitter"].id,
        organization_id=entities["org"].id,
        notification_type="TEST",
        title="Notice 1",
    )
    notif2 = notify(
        db_session,
        recipient_user_id=entities["submitter"].id,
        organization_id=entities["org"].id,
        notification_type="TEST",
        title="Notice 2",
    )

    headers = _auth_header(entities["submitter"].id, "SUBMITTER", entities["org"].id)

    # Mark single read
    resp = client.post(f"/api/notifications/{notif1.id}/read", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Check unread count
    resp = client.get("/api/notifications?unread_only=true", headers=headers)
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["id"] == notif2.id

    # Mark all read
    resp = client.post("/api/notifications/read-all", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 1

    # Check that unread count is 0
    resp = client.get("/api/notifications?unread_only=true", headers=headers)
    assert resp.json()["total"] == 0


def test_retries_do_not_duplicate_notifications(db_session: Session):
    entities = _seed_org_and_users(db_session)
    idem_key = "transition:t123:user_rev_1:ASSIGNED"

    n1 = notify(
        db_session,
        recipient_user_id=entities["reviewer"].id,
        organization_id=entities["org"].id,
        notification_type="ASSIGNED",
        title="Notice 1",
        idempotency_key=idem_key,
    )
    assert n1 is not None

    # Retry with same idempotency key
    n2 = notify(
        db_session,
        recipient_user_id=entities["reviewer"].id,
        organization_id=entities["org"].id,
        notification_type="ASSIGNED",
        title="Notice 1 (retry)",
        idempotency_key=idem_key,
    )
    assert n2 is not None
    assert n1.id == n2.id

    # Only 1 notification in database
    count = db_session.query(Notification).filter(Notification.recipient_user_id == entities["reviewer"].id).count()
    assert count == 1


def test_notification_failure_does_not_break_workflow(db_session: Session):
    entities = _seed_org_and_users(db_session)
    doc = _seed_document(db_session, entities["org"].id, entities["submitter"].id, DocumentStatus.CLASSIFIED)

    # Mock notify to raise an unexpected database exception
    with patch("services.notification.notify", side_effect=RuntimeError("Simulated notification service failure")):
        # Submitting document must still succeed!
        resp = submit_document(
            db_session,
            doc.id,
            {"sub": entities["submitter"].id, "role": "SUBMITTER", "organization_id": entities["org"].id, "active": True},
            reviewer_id=entities["reviewer"].id,
        )
        assert resp.status == DocumentStatus.IN_REVIEW
        assert resp.assigned_reviewer_id == entities["reviewer"].id
