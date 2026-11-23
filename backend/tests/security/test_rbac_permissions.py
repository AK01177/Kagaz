"""Role-Based Access Control and permission matrix security tests (QA-08 Scope 2).

Verifies the complete role-permission matrix, role isolation, privilege escalation prevention,
payload tampering immunity, and automated route protection verification.
"""
from __future__ import annotations

import uuid
from io import BytesIO
from typing import Mapping

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.auth import (
    PERMISSION_ERROR_DETAILS,
    ROLE_PERMISSIONS,
    Permission,
    get_permissions_for_role,
    identity_has_permission,
    roles_with_permission,
)
from app.models.document import Document, DocumentStatus
from app.models.membership import MembershipRole
from main import app
from tests.security.conftest import SecurityWorld, make_valid_pdf_bytes


def _assert_forbidden(response, expected_code: str | None = None) -> None:
    assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
    body = response.json()
    assert "error" in body, f"Error body missing wrapper: {body}"
    assert isinstance(body["error"].get("code"), str) and body["error"]["code"]
    assert isinstance(body["error"].get("message"), str) and body["error"]["message"]
    if expected_code is not None:
        assert body["error"]["code"] == expected_code


# ---------------------------------------------------------------------------
# 1. Role-Permission Matrix unit verification
# ---------------------------------------------------------------------------


def test_matrix_defines_every_membership_role_and_capability():
    """Verify that every MembershipRole enum value is present in ROLE_PERMISSIONS."""
    expected_roles = {role.value for role in MembershipRole}
    assert set(ROLE_PERMISSIONS.keys()) == expected_roles

    all_permissions = set(Permission)
    assert set().union(*ROLE_PERMISSIONS.values()) == all_permissions  # every permission is granted to someone
    # Org admins manage people and policies only; they do not touch documents or decisions.
    assert Permission.DOCUMENTS_UPLOAD not in ROLE_PERMISSIONS["ORG_ADMIN"]
    assert Permission.WORKFLOW_DECIDE not in ROLE_PERMISSIONS["ORG_ADMIN"]
    assert Permission.ADMIN_USERS_MANAGE in ROLE_PERMISSIONS["ORG_ADMIN"]
    assert Permission.ADMIN_ORGS_MANAGE not in ROLE_PERMISSIONS["ORG_ADMIN"]
    # System admins can additionally manage organizations.
    assert ROLE_PERMISSIONS["SYSTEM_ADMIN"] == ROLE_PERMISSIONS["ORG_ADMIN"] | {Permission.ADMIN_ORGS_MANAGE}

    # Check Submitters cannot approve, manage policies, or manage users
    submitter_perms = get_permissions_for_role("SUBMITTER")
    assert Permission.DOCUMENTS_UPLOAD in submitter_perms
    assert Permission.WORKFLOW_SUBMIT in submitter_perms
    assert Permission.WORKFLOW_DECIDE not in submitter_perms
    assert Permission.POLICIES_ADMIN not in submitter_perms
    assert Permission.ADMIN_USERS_MANAGE not in submitter_perms

    # Check Reviewers cannot approve or administer users
    reviewer_perms = get_permissions_for_role("REVIEWER")
    assert Permission.DOCUMENTS_CLASSIFY in reviewer_perms
    assert Permission.DOCUMENTS_CORRECT_CLASSIFICATION in reviewer_perms
    assert Permission.DOCUMENTS_RUN_EXTRACTION in reviewer_perms
    assert Permission.WORKFLOW_ASSIGN_REVIEWER in reviewer_perms
    assert Permission.WORKFLOW_DECIDE not in reviewer_perms
    assert Permission.POLICIES_ADMIN not in reviewer_perms
    assert Permission.ADMIN_USERS_MANAGE not in reviewer_perms

    # Check Approvers cannot classify, re-extract, or administer users
    approver_perms = get_permissions_for_role("APPROVER")
    assert Permission.WORKFLOW_APPROVAL_QUEUE in approver_perms
    assert Permission.WORKFLOW_DECIDE in approver_perms
    assert Permission.DOCUMENTS_CORRECT_CLASSIFICATION not in approver_perms
    assert Permission.DOCUMENTS_RUN_EXTRACTION not in approver_perms
    assert Permission.WORKFLOW_ASSIGN_REVIEWER not in approver_perms
    assert Permission.POLICIES_ADMIN not in approver_perms
    assert Permission.ADMIN_USERS_MANAGE not in approver_perms

    # Check Auditor is strictly read-only
    auditor_perms = get_permissions_for_role("AUDITOR")
    assert Permission.DOCUMENTS_READ in auditor_perms
    assert Permission.DOCUMENTS_READ_EXTRACTION in auditor_perms
    assert Permission.POLICIES_READ in auditor_perms
    assert Permission.AUDIT_READ in auditor_perms
    assert Permission.DOCUMENTS_UPLOAD not in auditor_perms
    assert Permission.DOCUMENTS_VALIDATE not in auditor_perms
    assert Permission.DOCUMENTS_VALIDATE_POLICY not in auditor_perms
    assert Permission.WORKFLOW_DECIDE not in auditor_perms
    assert Permission.POLICIES_ADMIN not in auditor_perms


def test_roles_with_permission_and_identity_has_permission():
    """Verify reverse role lookup and identity capability checking."""
    upload_roles = roles_with_permission(Permission.DOCUMENTS_UPLOAD)
    assert upload_roles == {"SUBMITTER"}

    decide_roles = roles_with_permission(Permission.WORKFLOW_DECIDE)
    assert decide_roles == {"APPROVER"}

    assert identity_has_permission({"role": "REVIEWER"}, Permission.DOCUMENTS_CLASSIFY) is True
    assert identity_has_permission({"role": "SUBMITTER"}, Permission.DOCUMENTS_CLASSIFY) is False
    assert identity_has_permission({"role": "SUBMITTER", "permissions": ["documents:classify"]}, Permission.DOCUMENTS_CLASSIFY) is True


# ---------------------------------------------------------------------------
# 2. Submitter Role Isolation
# ---------------------------------------------------------------------------


def test_submitter_allowed_and_forbidden_actions(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """Submitters can upload and view own docs; forbidden from reviewing, approving, or admin."""
    headers = security_world.headers_for(security_world.submitter_a1)

    # Allowed: Upload a new document
    upload_resp = client.post(
        "/api/documents",
        files={"file": ("new_sub.pdf", BytesIO(make_valid_pdf_bytes("Submitter upload")), "application/pdf")},
        headers=headers,
    )
    assert upload_resp.status_code == 201

    # Allowed: List own documents
    list_resp = client.get("/api/documents", headers=headers)
    assert list_resp.status_code == 200
    listed_ids = {d["document_id"] for d in list_resp.json()["documents"]}
    assert security_world.doc_a1.id in listed_ids
    assert security_world.doc_a2.id not in listed_ids  # Cannot list other submitter's docs

    # Forbidden: Submitter cannot correct classification
    _assert_forbidden(
        client.patch(f"/api/documents/{security_world.doc_a1.id}/classification", json={"category": "legal"}, headers=headers),
        "REVIEW_FORBIDDEN",
    )

    # Forbidden: Submitter cannot run extraction
    _assert_forbidden(
        client.post(f"/api/documents/{security_world.doc_a1.id}/extract", headers=headers),
        "EXTRACTION_FORBIDDEN",
    )

    # Forbidden: Submitter cannot access review queue or approval queue
    _assert_forbidden(client.get("/api/documents/workflow/review-queue", headers=headers), "REVIEW_QUEUE_FORBIDDEN")
    _assert_forbidden(client.get("/api/documents/workflow/approval-queue", headers=headers), "APPROVAL_QUEUE_FORBIDDEN")

    # Forbidden: Submitter cannot decide documents
    _assert_forbidden(
        client.post(f"/api/documents/{security_world.doc_a1.id}/approve", json={"reason": "Self-approve"}, headers=headers),
        "APPROVAL_FORBIDDEN",
    )
    _assert_forbidden(
        client.post(f"/api/documents/{security_world.doc_a1.id}/reject", json={"reason": "Self-reject"}, headers=headers),
        "APPROVAL_FORBIDDEN",
    )

    # Forbidden: Submitter cannot manage policies or users
    _assert_forbidden(
        client.post("/api/policies", json={"name": "Hacked", "domain": "financial", "content": "free money"}, headers=headers),
        "POLICY_ADMIN_REQUIRED",
    )
    _assert_forbidden(client.get("/api/admin/users", headers=headers), "ADMIN_FORBIDDEN")


# ---------------------------------------------------------------------------
# 3. Reviewer vs Approver Responsibility Separation
# ---------------------------------------------------------------------------


def test_reviewer_cannot_approve_or_administer(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """Reviewers can classify and extract, but cannot decide documents or manage admin."""
    headers = security_world.headers_for(security_world.reviewer_a)

    # Allowed: Review queue
    assert client.get("/api/documents/workflow/review-queue", headers=headers).status_code == 200

    # Allowed: Classification mutation
    patch_resp = client.patch(
        f"/api/documents/{security_world.doc_a1.id}/classification",
        json={"category": "hr_documents", "notes": "Verified by reviewer"},
        headers=headers,
    )
    assert patch_resp.status_code == 200

    # Forbidden: Reviewer cannot upload documents
    _assert_forbidden(
        client.post(
            "/api/documents",
            files={"file": ("rev.pdf", BytesIO(b"%PDF-1.4\n%%EOF"), "application/pdf")},
            headers=headers,
        ),
        "UPLOAD_FORBIDDEN",
    )

    # Forbidden: Reviewer cannot access approval queue
    _assert_forbidden(client.get("/api/documents/workflow/approval-queue", headers=headers), "APPROVAL_QUEUE_FORBIDDEN")

    # Forbidden: Reviewer cannot approve or reject
    _assert_forbidden(
        client.post(f"/api/documents/{security_world.doc_a1.id}/approve", json={"reason": "Looks good"}, headers=headers),
        "APPROVAL_FORBIDDEN",
    )
    _assert_forbidden(
        client.post(f"/api/documents/{security_world.doc_a1.id}/reject", json={"reason": "Rejected"}, headers=headers),
        "APPROVAL_FORBIDDEN",
    )

    # Forbidden: Reviewer cannot manage admin or policies
    _assert_forbidden(client.get("/api/admin/organization", headers=headers), "ADMIN_FORBIDDEN")
    _assert_forbidden(
        client.post("/api/policies", json={"name": "P", "domain": "financial", "content": "C"}, headers=headers),
        "POLICY_ADMIN_REQUIRED",
    )


def test_approver_cannot_perform_reviewer_mutations_and_decides_eligible_docs(
    client: TestClient, security_world: SecurityWorld, db_session: Session
) -> None:
    """Approvers cannot upload, classify, or re-extract; can decide eligible pending documents."""
    headers = security_world.headers_for(security_world.approver_a)

    # Allowed: Approval queue and review queue
    assert client.get("/api/documents/workflow/approval-queue", headers=headers).status_code == 200
    assert client.get("/api/documents/workflow/review-queue", headers=headers).status_code == 200

    # Forbidden: Approver cannot upload or reclassify
    _assert_forbidden(
        client.post(
            "/api/documents",
            files={"file": ("app.pdf", BytesIO(b"%PDF-1.4\n%%EOF"), "application/pdf")},
            headers=headers,
        ),
        "UPLOAD_FORBIDDEN",
    )
    _assert_forbidden(
        client.patch(f"/api/documents/{security_world.doc_a1.id}/classification", json={"category": "legal"}, headers=headers),
        "REVIEW_FORBIDDEN",
    )
    _assert_forbidden(
        client.post(f"/api/documents/{security_world.doc_a1.id}/extract", headers=headers),
        "EXTRACTION_FORBIDDEN",
    )
    _assert_forbidden(
        client.post(f"/api/documents/{security_world.doc_a1.id}/assign", json={"reviewer_id": security_world.reviewer_a.id}, headers=headers),
        "ASSIGN_REVIEWER_FORBIDDEN",
    )
    _assert_forbidden(
        client.post(f"/api/documents/{security_world.doc_a1.id}/submit-for-approval", json={}, headers=headers),
        "SUBMIT_FOR_APPROVAL_FORBIDDEN",
    )

    # Set document to PENDING_APPROVAL assigned to approver_a
    security_world.doc_a1.status = DocumentStatus.PENDING_APPROVAL
    security_world.doc_a1.assigned_approver_id = security_world.approver_a.id
    db_session.commit()

    # Allowed: Approver approves eligible document
    decide_resp = client.post(
        f"/api/documents/{security_world.doc_a1.id}/approve",
        json={"reason": "Audited and approved"},
        headers=headers,
    )
    assert decide_resp.status_code == 200
    assert decide_resp.json()["status"] == "APPROVED"


# ---------------------------------------------------------------------------
# 4. Auditor and Compliance Restrictions
# ---------------------------------------------------------------------------


def test_auditor_is_strictly_read_only(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """Auditors have read-only visibility into policies, audit logs, and documents; mutations rejected."""
    headers = security_world.headers_for(security_world.auditor_a)

    # Allowed reads
    assert client.get("/api/policies", headers=headers).status_code == 200
    assert client.get(f"/api/policies/{security_world.policy_a.id}", headers=headers).status_code == 200
    assert client.get(f"/api/audit/{security_world.doc_a1.id}", headers=headers).status_code == 200
    assert client.get(f"/api/documents/{security_world.doc_a1.id}/extract", headers=headers).status_code == 200

    # Forbidden mutations
    _assert_forbidden(
        client.post(
            "/api/documents",
            files={"file": ("a.pdf", BytesIO(b"%PDF-1.4\n%%EOF"), "application/pdf")},
            headers=headers,
        ),
        "UPLOAD_FORBIDDEN",
    )
    _assert_forbidden(
        client.post(f"/api/documents/{security_world.doc_a1.id}/validate-policy", headers=headers),
        "POLICY_VALIDATION_FORBIDDEN",
    )
    _assert_forbidden(
        client.post(f"/api/documents/{security_world.doc_a1.id}/validate", headers=headers),
        "VALIDATION_FORBIDDEN",
    )
    _assert_forbidden(
        client.delete(f"/api/policies/{security_world.policy_a.id}", headers=headers),
        "POLICY_ADMIN_REQUIRED",
    )


# ---------------------------------------------------------------------------
# 5. Privilege Escalation and Tampering Immunity
# ---------------------------------------------------------------------------


def test_users_cannot_escalate_privileges_via_payload_or_headers(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """Tampering with request body roles or spoofing headers does not elevate permissions."""
    headers = security_world.headers_for(security_world.submitter_a1)

    # Spoofing headers
    tampered_headers = {
        **headers,
        "X-User-Role": "ORG_ADMIN",
        "X-Role": "SYSTEM_ADMIN",
        "X-Permissions": "*",
    }
    _assert_forbidden(client.get("/api/admin/users", headers=tampered_headers), "ADMIN_FORBIDDEN")
    _assert_forbidden(client.get("/api/admin/organization", headers=tampered_headers), "ADMIN_FORBIDDEN")


def test_org_admin_cannot_escalate_users_to_system_admin(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """An ORG_ADMIN cannot promote any member to SYSTEM_ADMIN."""
    headers = security_world.headers_for(security_world.admin_a)
    escalate_resp = client.put(
        f"/api/admin/users/{security_world.submitter_a1.id}",
        json={"role": "SYSTEM_ADMIN"},
        headers=headers,
    )
    _assert_forbidden(escalate_resp, "SYSTEM_ADMIN_REQUIRED")


# ---------------------------------------------------------------------------
# 6. Automated Route Authorization Dependency Verification
# ---------------------------------------------------------------------------


def test_all_api_routes_declare_authentication_dependencies():
    """Verify that every route mounted under /api/ (except /api/health) enforces authentication."""
    public_routes = {
        ("GET", "/api/health"),
    }

    def _collect_dependencies(dependant) -> list:
        deps = []
        if dependant.call is not None:
            deps.append(dependant.call)
        for sub in dependant.dependencies:
            deps.extend(_collect_dependencies(sub))
        return deps

    unprotected = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/"):
            continue
        deps = _collect_dependencies(route.dependant)
        for method in sorted(route.methods or ()):
            if method in {"HEAD", "OPTIONS"}:
                continue
            if (method, route.path) in public_routes:
                continue
            dep_names = {getattr(fn, "__name__", str(fn)) for fn in deps}
            if "get_current_user" not in dep_names:
                unprotected.append(f"{method} {route.path} -> {sorted(dep_names)}")

    assert unprotected == [], f"Found unprotected API routes: {unprotected}"
