"""Comprehensive RBAC & backend endpoint authorization tests (BE role permissions)."""
from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import Permission, ROLE_PERMISSIONS, create_access_token, get_auth_db
from app.core.permissions import get_permissions_for_role, roles_with_permission
from app.crud.user import create_user
from app.db.base import Base
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.policy import Policy
from app.schemas.user import UserCreate
from main import app

TEST_JWT_SECRET = "rbac-role-permission-test-secret-32-bytes"


@pytest.fixture(autouse=True)
def _rbac_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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


def _seed_org(db: Session, org_id: str, slug: str) -> Organization:
    org = Organization(id=org_id, name=f"Org {slug}", slug=slug, is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _seed_member(
    db: Session,
    *,
    org_id: str,
    email: str,
    role: MembershipRole,
) -> tuple[str, str]:
    user = create_user(
        db,
        UserCreate(
            email=email,
            password="StrongPassword123!",
            full_name=email.split("@")[0],
        ),
    )
    membership = Membership(
        id=str(uuid.uuid4()),
        user_id=user.id,
        organization_id=org_id,
        role=role,
        is_active=True,
    )
    db.add(membership)
    db.commit()
    token = create_access_token(
        user_id=user.id,
        role=role.value,
        organization_id=org_id,
    )
    return user.id, token


def _seed_document(
    db: Session,
    *,
    org_id: str,
    uploaded_by: str,
    status: DocumentStatus = DocumentStatus.EXTRACTED,
    assigned_reviewer_id: str | None = None,
    assigned_approver_id: str | None = None,
    classification: str = "invoice",
) -> Document:
    doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        uploaded_by=uploaded_by,
        filename="sample.pdf",
        file_type="application/pdf",
        file_size=128,
        storage_path="documents/sample.pdf",
        status=status,
        classification=classification,
        assigned_reviewer_id=assigned_reviewer_id,
        assigned_approver_id=assigned_approver_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _assert_forbidden(response, expected_code: str | None = None) -> None:
    assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
    body = response.json()
    assert "error" in body, f"Consistent error wrapper missing: {body}"
    assert isinstance(body["error"].get("code"), str) and body["error"]["code"]
    assert isinstance(body["error"].get("message"), str) and body["error"]["message"]
    if expected_code is not None:
        assert body["error"]["code"] == expected_code


# ---------------------------------------------------------------------------
# 1. Role-Permission Matrix unit verification
# ---------------------------------------------------------------------------


def test_role_permission_matrix_defines_every_membership_role_and_capability():
    expected_roles = {role.value for role in MembershipRole}
    assert set(ROLE_PERMISSIONS.keys()) == expected_roles

    # Every declared Permission is granted to at least one role (ORG_ADMIN/SYSTEM_ADMIN).
    all_permissions = set(Permission)
    assert ROLE_PERMISSIONS["ORG_ADMIN"] == all_permissions
    assert ROLE_PERMISSIONS["SYSTEM_ADMIN"] == all_permissions

    # Submitters cannot approve, administer policies, or administer users.
    submitter_perms = get_permissions_for_role("SUBMITTER")
    assert Permission.DOCUMENTS_UPLOAD in submitter_perms
    assert Permission.WORKFLOW_SUBMIT in submitter_perms
    assert Permission.WORKFLOW_DECIDE not in submitter_perms
    assert Permission.WORKFLOW_APPROVAL_QUEUE not in submitter_perms
    assert Permission.POLICIES_ADMIN not in submitter_perms
    assert Permission.ADMIN_USERS_MANAGE not in submitter_perms

    # Reviewers cannot approve or administer the organization.
    reviewer_perms = get_permissions_for_role("REVIEWER")
    assert Permission.WORKFLOW_ASSIGN_REVIEWER in reviewer_perms
    assert Permission.WORKFLOW_SUBMIT_FOR_APPROVAL in reviewer_perms
    assert Permission.DOCUMENTS_CORRECT_CLASSIFICATION in reviewer_perms
    assert Permission.WORKFLOW_DECIDE not in reviewer_perms
    assert Permission.WORKFLOW_APPROVAL_QUEUE not in reviewer_perms
    assert Permission.POLICIES_ADMIN not in reviewer_perms
    assert Permission.ADMIN_ORG_READ not in reviewer_perms
    assert Permission.ADMIN_USERS_MANAGE not in reviewer_perms

    # Approvers decide & inspect queues, without classification mutation or admin control.
    approver_perms = get_permissions_for_role("APPROVER")
    assert Permission.WORKFLOW_APPROVAL_QUEUE in approver_perms
    assert Permission.WORKFLOW_DECIDE in approver_perms
    assert Permission.WORKFLOW_ASSIGN_REVIEWER not in approver_perms
    assert Permission.WORKFLOW_SUBMIT_FOR_APPROVAL not in approver_perms
    assert Permission.DOCUMENTS_CORRECT_CLASSIFICATION not in approver_perms
    assert Permission.POLICIES_ADMIN not in approver_perms
    assert Permission.ADMIN_USERS_MANAGE not in approver_perms

    # Read-only Auditor cannot mutate workflow or run policy validations.
    auditor_perms = get_permissions_for_role("AUDITOR")
    assert Permission.AUDIT_READ in auditor_perms
    assert Permission.DOCUMENTS_VALIDATE_POLICY not in auditor_perms
    assert Permission.WORKFLOW_DECIDE not in auditor_perms

    assert roles_with_permission(Permission.ADMIN_USERS_MANAGE) == frozenset(
        {"ORG_ADMIN", "SYSTEM_ADMIN"}
    )


# ---------------------------------------------------------------------------
# 2. Submitter restrictions and explicit authorization behavior
# ---------------------------------------------------------------------------


def test_submitter_cannot_approve_or_administer_unless_explicitly_authorized(
    client: TestClient, db_session: Session
):
    _seed_org(db_session, "org-alpha", "alpha")
    submitter_id, submitter_token = _seed_member(
        db_session,
        org_id="org-alpha",
        email="sub1@alpha.test",
        role=MembershipRole.SUBMITTER,
    )
    other_submitter_id, _ = _seed_member(
        db_session,
        org_id="org-alpha",
        email="sub2@alpha.test",
        role=MembershipRole.SUBMITTER,
    )
    _admin_id, admin_token = _seed_member(
        db_session,
        org_id="org-alpha",
        email="admin@alpha.test",
        role=MembershipRole.ORG_ADMIN,
    )

    own_doc = _seed_document(
        db_session,
        org_id="org-alpha",
        uploaded_by=submitter_id,
        status=DocumentStatus.PENDING_APPROVAL,
    )
    foreign_doc = _seed_document(
        db_session,
        org_id="org-alpha",
        uploaded_by=other_submitter_id,
        status=DocumentStatus.EXTRACTED,
    )

    headers = {"Authorization": f"Bearer {submitter_token}"}

    # Submitter cannot access approval queue, approve/reject, or administer org/policies.
    _assert_forbidden(client.get("/api/documents/workflow/approval-queue", headers=headers), "APPROVAL_QUEUE_FORBIDDEN")
    _assert_forbidden(
        client.post(f"/api/documents/{own_doc.id}/approve", json={"reason": "Self approve"}, headers=headers),
        "APPROVAL_FORBIDDEN",
    )
    _assert_forbidden(
        client.post(f"/api/documents/{own_doc.id}/reject", json={"reason": "Self reject"}, headers=headers),
        "APPROVAL_FORBIDDEN",
    )
    _assert_forbidden(client.get("/api/admin/organization", headers=headers), "ADMIN_FORBIDDEN")
    _assert_forbidden(
        client.post("/api/policies", json={"name": "P", "domain": "finance"}, headers=headers),
        "POLICY_ADMIN_REQUIRED",
    )

    # Submitter cannot inspect another submitter's document in the same org.
    _assert_forbidden(client.get(f"/api/documents/{foreign_doc.id}", headers=headers), "DOCUMENT_ACCESS_FORBIDDEN")

    # Org Admin explicitly authorizes the submitter as APPROVER; backend immediately grants decision power.
    grant = client.put(
        f"/api/admin/users/{submitter_id}",
        json={"role": "APPROVER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert grant.status_code == 200
    assert grant.json()["role"] == "APPROVER"

    # Even reusing the existing token, server-side membership lookup resolves updated APPROVER role.
    approve = client.post(
        f"/api/documents/{own_doc.id}/approve",
        json={"reason": "Explicitly authorized"},
        headers=headers,
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "APPROVED"

    # Explicit server-signed permission grant also works via create_access_token in stateless/delegated mode.
    doc_for_grant = _seed_document(
        db_session,
        org_id="org-alpha",
        uploaded_by=other_submitter_id,
        status=DocumentStatus.PENDING_APPROVAL,
    )
    explicit_token = create_access_token(
        user_id=other_submitter_id,
        role="SUBMITTER",
        organization_id="org-alpha",
        permissions=[Permission.WORKFLOW_DECIDE.value],
    )
    app.dependency_overrides[get_auth_db] = lambda: None
    try:
        explicit_resp = client.post(
            f"/api/documents/{doc_for_grant.id}/approve",
            json={"reason": "Scoped delegation"},
            headers={"Authorization": f"Bearer {explicit_token}"},
        )
    finally:
        app.dependency_overrides[get_auth_db] = lambda: db_session
    assert explicit_resp.status_code == 200
    assert explicit_resp.json()["status"] == "APPROVED"


# ---------------------------------------------------------------------------
# 3. Reviewer vs. Approver separation & eligible document guards
# ---------------------------------------------------------------------------


def test_reviewer_cannot_approve_or_administer_org(client: TestClient, db_session: Session):
    _seed_org(db_session, "org-beta", "beta")
    submitter_id, _ = _seed_member(
        db_session, org_id="org-beta", email="sub@beta.test", role=MembershipRole.SUBMITTER
    )
    reviewer_id, reviewer_token = _seed_member(
        db_session, org_id="org-beta", email="rev@beta.test", role=MembershipRole.REVIEWER
    )
    doc = _seed_document(
        db_session,
        org_id="org-beta",
        uploaded_by=submitter_id,
        status=DocumentStatus.PENDING_APPROVAL,
        assigned_reviewer_id=reviewer_id,
    )
    headers = {"Authorization": f"Bearer {reviewer_token}"}

    # Reviewer cannot inspect approval queue or make final approval/rejection decisions.
    _assert_forbidden(client.get("/api/documents/workflow/approval-queue", headers=headers), "APPROVAL_QUEUE_FORBIDDEN")
    _assert_forbidden(
        client.post(f"/api/documents/{doc.id}/approve", json={"reason": "Looks ok"}, headers=headers),
        "APPROVAL_FORBIDDEN",
    )
    _assert_forbidden(
        client.post(f"/api/documents/{doc.id}/reject", json={"reason": "Nope"}, headers=headers),
        "APPROVAL_FORBIDDEN",
    )

    # Reviewer cannot administer the organization or policies unless separately authorized.
    _assert_forbidden(client.get("/api/admin/organization", headers=headers), "ADMIN_FORBIDDEN")
    _assert_forbidden(client.get("/api/admin/users", headers=headers), "ADMIN_FORBIDDEN")
    _assert_forbidden(
        client.put(f"/api/admin/users/{submitter_id}", json={"role": "ORG_ADMIN"}, headers=headers),
        "ADMIN_FORBIDDEN",
    )
    _assert_forbidden(
        client.post("/api/policies", json={"name": "Expense", "domain": "finance"}, headers=headers),
        "POLICY_ADMIN_REQUIRED",
    )
    _assert_forbidden(
        client.post(
            "/api/policies/ingest",
            data={"policy_name": "Sec", "version": "v1"},
            files={"file": ("p.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")},
            headers=headers,
        ),
        "POLICY_ADMIN_REQUIRED",
    )


def test_approver_cannot_perform_reviewer_mutation_and_decides_only_eligible_docs(
    client: TestClient, db_session: Session
):
    _seed_org(db_session, "org-gamma", "gamma")
    _seed_org(db_session, "org-other", "other")

    sub_id, _ = _seed_member(
        db_session, org_id="org-gamma", email="sub@gamma.test", role=MembershipRole.SUBMITTER
    )
    rev_id, _ = _seed_member(
        db_session, org_id="org-gamma", email="rev@gamma.test", role=MembershipRole.REVIEWER
    )
    approver1_id, approver1_token = _seed_member(
        db_session, org_id="org-gamma", email="app1@gamma.test", role=MembershipRole.APPROVER
    )
    approver2_id, _ = _seed_member(
        db_session, org_id="org-gamma", email="app2@gamma.test", role=MembershipRole.APPROVER
    )
    other_sub_id, _ = _seed_member(
        db_session, org_id="org-other", email="sub@other.test", role=MembershipRole.SUBMITTER
    )

    headers = {"Authorization": f"Bearer {approver1_token}"}

    # Approver cannot perform upload, classification, extraction, reviewer assignment, or submit-for-approval.
    submitted_doc = _seed_document(
        db_session, org_id="org-gamma", uploaded_by=sub_id, status=DocumentStatus.SUBMITTED
    )
    _assert_forbidden(
        client.post(
            "/api/documents",
            files={"file": ("doc.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")},
            headers=headers,
        ),
        "UPLOAD_FORBIDDEN",
    )
    _assert_forbidden(client.post(f"/api/documents/{submitted_doc.id}/classify", headers=headers), "CLASSIFICATION_FORBIDDEN")
    _assert_forbidden(
        client.patch(f"/api/documents/{submitted_doc.id}/classification", json={"category": "legal"}, headers=headers),
        "REVIEW_FORBIDDEN",
    )
    _assert_forbidden(client.post(f"/api/documents/{submitted_doc.id}/extract", headers=headers), "EXTRACTION_FORBIDDEN")
    _assert_forbidden(
        client.post(f"/api/documents/{submitted_doc.id}/assign", json={"reviewer_id": rev_id}, headers=headers),
        "ASSIGN_REVIEWER_FORBIDDEN",
    )
    _assert_forbidden(
        client.post(f"/api/documents/{submitted_doc.id}/submit-for-approval", json={}, headers=headers),
        "SUBMIT_FOR_APPROVAL_FORBIDDEN",
    )

    # Ineligible document state (SUBMITTED) cannot be approved directly.
    ineligible_resp = client.post(
        f"/api/documents/{submitted_doc.id}/approve",
        json={"reason": "Bypass review"},
        headers=headers,
    )
    assert ineligible_resp.status_code == 409
    assert ineligible_resp.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    # Document in another org cannot be decided by org-gamma approver.
    foreign_doc = _seed_document(
        db_session, org_id="org-other", uploaded_by=other_sub_id, status=DocumentStatus.PENDING_APPROVAL
    )
    foreign_resp = client.post(
        f"/api/documents/{foreign_doc.id}/approve",
        json={"reason": "Cross tenant"},
        headers=headers,
    )
    assert foreign_resp.status_code in {403, 404}

    # Document assigned to a different approver cannot be decided by approver1.
    other_assigned_doc = _seed_document(
        db_session,
        org_id="org-gamma",
        uploaded_by=sub_id,
        status=DocumentStatus.PENDING_APPROVAL,
        assigned_approver_id=approver2_id,
    )
    _assert_forbidden(
        client.post(
            f"/api/documents/{other_assigned_doc.id}/approve",
            json={"reason": "Steal approval"},
            headers=headers,
        ),
        "WORKFLOW_FORBIDDEN",
    )

    # Eligible document assigned to approver1 in own org succeeds.
    eligible_doc = _seed_document(
        db_session,
        org_id="org-gamma",
        uploaded_by=sub_id,
        status=DocumentStatus.PENDING_APPROVAL,
        assigned_approver_id=approver1_id,
    )
    ok_resp = client.post(
        f"/api/documents/{eligible_doc.id}/approve",
        json={"reason": "Policy checks verified"},
        headers=headers,
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["status"] == "APPROVED"


# ---------------------------------------------------------------------------
# 4. Upload, Policy, Validation, and Admin cross-org checks
# ---------------------------------------------------------------------------


def test_auditor_and_compliance_cannot_mutate_policies_or_run_forbidden_actions(
    client: TestClient, db_session: Session
):
    _seed_org(db_session, "org-delta", "delta")
    sub_id, _ = _seed_member(
        db_session, org_id="org-delta", email="sub@delta.test", role=MembershipRole.SUBMITTER
    )
    _, auditor_token = _seed_member(
        db_session, org_id="org-delta", email="aud@delta.test", role=MembershipRole.AUDITOR
    )
    policy = Policy(
        id=str(uuid.uuid4()),
        organization_id="org-delta",
        name="Retention Policy",
        domain="legal",
        content="All financial and legal records must be retained for at least 7 years.",
        is_active=True,
    )
    doc = _seed_document(db_session, org_id="org-delta", uploaded_by=sub_id, status=DocumentStatus.EXTRACTED)
    db_session.add(policy)
    db_session.commit()

    headers = {"Authorization": f"Bearer {auditor_token}"}
    # Read-only access allowed for auditor.
    assert client.get("/api/policies", headers=headers).status_code == 200
    assert client.get(f"/api/policies/{policy.id}", headers=headers).status_code == 200
    assert client.get(f"/api/audit/{doc.id}", headers=headers).status_code == 200

    # Mutations / policy validation / policy admin denied cleanly with 403.
    _assert_forbidden(
        client.post(f"/api/documents/{doc.id}/validate-policy", headers=headers),
        "POLICY_VALIDATION_FORBIDDEN",
    )
    _assert_forbidden(client.post(f"/api/documents/{doc.id}/validate", headers=headers), "VALIDATION_FORBIDDEN")
    _assert_forbidden(client.delete(f"/api/policies/{policy.id}", headers=headers), "POLICY_ADMIN_REQUIRED")
    _assert_forbidden(
        client.post(f"/api/documents/{doc.id}/comments", json={"comment": "hi"}, headers=headers),
        "REVIEW_COMMENT_FORBIDDEN",
    )


def test_org_admin_cannot_administer_another_organization_or_grant_system_admin(
    client: TestClient, db_session: Session
):
    _seed_org(db_session, "org-one", "one")
    _seed_org(db_session, "org-two", "two")

    _admin1_id, admin1_token = _seed_member(
        db_session, org_id="org-one", email="admin@one.test", role=MembershipRole.ORG_ADMIN
    )
    member1_id, _ = _seed_member(
        db_session, org_id="org-one", email="user@one.test", role=MembershipRole.SUBMITTER
    )
    member2_id, _ = _seed_member(
        db_session, org_id="org-two", email="user@two.test", role=MembershipRole.SUBMITTER
    )

    headers = {"Authorization": f"Bearer {admin1_token}"}

    # Own organization works.
    org_resp = client.get("/api/admin/organization", headers=headers)
    assert org_resp.status_code == 200
    assert org_resp.json()["organization_id"] == "org-one"

    users_resp = client.get("/api/admin/users", headers=headers)
    assert users_resp.status_code == 200
    returned_ids = {u["user_id"] for u in users_resp.json()["users"]}
    assert member1_id in returned_ids
    assert member2_id not in returned_ids

    # Query/body/header targeting org-two fails closed with 403.
    _assert_forbidden(
        client.get("/api/admin/organization", params={"organization_id": "org-two"}, headers=headers),
        "ADMIN_TENANT_FORBIDDEN",
    )
    _assert_forbidden(
        client.get("/api/admin/users", params={"organization_id": "org-two"}, headers=headers),
        "ADMIN_TENANT_FORBIDDEN",
    )
    _assert_forbidden(
        client.put(
            f"/api/admin/users/{member2_id}",
            json={"role": "ORG_ADMIN", "organization_id": "org-two"},
            headers=headers,
        ),
        "ADMIN_TENANT_FORBIDDEN",
    )
    _assert_forbidden(
        client.get("/api/admin/users", headers={**headers, "X-Organization-Id": "org-two"}),
    )

    # Targeting a member from org-two without specifying org-two cannot find/modify them inside org-one.
    not_found = client.put(
        f"/api/admin/users/{member2_id}",
        json={"role": "REVIEWER"},
        headers=headers,
    )
    assert not_found.status_code == 404

    # ORG_ADMIN cannot escalate anyone to SYSTEM_ADMIN.
    _assert_forbidden(
        client.put(
            f"/api/admin/users/{member1_id}",
            json={"role": "SYSTEM_ADMIN"},
            headers=headers,
        ),
        "SYSTEM_ADMIN_REQUIRED",
    )

    # Attempting to forge roles via client headers never bypasses RBAC.
    _, sub_token = _seed_member(
        db_session, org_id="org-one", email="attacker@one.test", role=MembershipRole.SUBMITTER
    )
    _assert_forbidden(
        client.get(
            "/api/admin/users",
            headers={
                "Authorization": f"Bearer {sub_token}",
                "X-User-Role": "ORG_ADMIN",
                "X-Permissions": "*",
            },
        ),
        "ADMIN_FORBIDDEN",
    )


# ---------------------------------------------------------------------------
# 5. Automated FastAPI route authorization audit
# ---------------------------------------------------------------------------


def test_every_non_public_api_route_declares_authentication_dependency():
    public_routes = {
        ("GET", "/api/health"),
        ("POST", "/api/auth/login"),
    }

    def _collect_dependency_calls(dependant) -> list:
        calls = []
        if dependant.call is not None:
            calls.append(dependant.call)
        for sub in dependant.dependencies:
            calls.extend(_collect_dependency_calls(sub))
        return calls

    unprotected = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/"):
            continue
        calls = _collect_dependency_calls(route.dependant)
        for method in sorted(route.methods or ()):
            if method in {"HEAD", "OPTIONS"}:
                continue
            if (method, route.path) in public_routes:
                continue
            # All non-public /api/* routes must traverse get_current_user (directly or via require_permission).
            call_names = {getattr(fn, "__name__", str(fn)) for fn in calls}
            if "get_current_user" not in call_names:
                unprotected.append(f"{method} {route.path} -> {sorted(call_names)}")

    assert unprotected == [], f"Found unprotected API routes: {unprotected}"
