"""Tenant isolation and multi-tenancy boundary security tests (QA-08 Scope 3, 5, 6, 7, 8).

Verifies strict cross-organization isolation across documents, metadata, extractions,
policies, validation, workflow state machines, audit events, notifications, and admin endpoints.
"""
from __future__ import annotations

import json
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crud.extraction import (
    delete_extractions_by_document,
    get_document_extractions_summary,
    get_extractions_by_document,
)
from app.models.document import Document, DocumentStatus
from app.models.notification import Notification
from app.models.policy import Policy
from tests.security.conftest import SecurityWorld


def _assert_forbidden(response, expected_code: str | None = None) -> None:
    assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
    body = response.json()
    assert "error" in body, f"Error body missing wrapper: {body}"
    assert isinstance(body["error"].get("code"), str) and body["error"]["code"]
    if expected_code is not None:
        assert body["error"]["code"] == expected_code


# ---------------------------------------------------------------------------
# 1. Document & Metadata Tenant Isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_document_metadata_read_is_denied(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """A user in Org A cannot access documents belonging to Org B."""
    rev_a = security_world.headers_for(security_world.reviewer_a)

    # Org A reviewer accesses Org B document
    resp = client.get(f"/api/documents/{security_world.doc_b.id}", headers=rev_a)
    _assert_forbidden(resp, "TENANT_ACCESS_DENIED")

    # Org B user accesses Org A document
    sub_b = security_world.headers_for(security_world.submitter_b)
    resp_b = client.get(f"/api/documents/{security_world.doc_a1.id}", headers=sub_b)
    _assert_forbidden(resp_b, "TENANT_ACCESS_DENIED")


def test_document_listing_strictly_filters_by_organization(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """Document listing returns only documents belonging to the caller's active organization."""
    rev_a = security_world.headers_for(security_world.reviewer_a)
    resp_a = client.get("/api/documents", headers=rev_a)
    assert resp_a.status_code == 200
    docs_a = {d["document_id"] for d in resp_a.json()["documents"]}
    assert security_world.doc_a1.id in docs_a
    assert security_world.doc_a2.id in docs_a
    assert security_world.doc_b.id not in docs_a  # No cross-tenant document leak

    rev_b = security_world.headers_for(security_world.reviewer_b)
    resp_b = client.get("/api/documents", headers=rev_b)
    assert resp_b.status_code == 200
    docs_b = {d["document_id"] for d in resp_b.json()["documents"]}
    assert security_world.doc_b.id in docs_b
    assert security_world.doc_a1.id not in docs_b
    assert security_world.doc_a2.id not in docs_b


def test_submitter_isolation_within_same_organization(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """A SUBMITTER cannot access or list documents uploaded by other submitters in the same org."""
    sub_a1 = security_world.headers_for(security_world.submitter_a1)

    # Submitter A1 reads Submitter A2's document -> 403 DOCUMENT_ACCESS_FORBIDDEN
    resp = client.get(f"/api/documents/{security_world.doc_a2.id}", headers=sub_a1)
    _assert_forbidden(resp, "DOCUMENT_ACCESS_FORBIDDEN")

    # Submitter A1 listing returns only their own upload
    list_resp = client.get("/api/documents", headers=sub_a1)
    assert list_resp.status_code == 200
    docs = {d["document_id"] for d in list_resp.json()["documents"]}
    assert security_world.doc_a1.id in docs
    assert security_world.doc_a2.id not in docs


def test_cross_tenant_document_classification_mutations_are_denied(
    client: TestClient, security_world: SecurityWorld, db_session: Session
) -> None:
    """A reviewer in Org A cannot classify or correct classifications on Org B documents."""
    rev_a = security_world.headers_for(security_world.reviewer_a)

    # Trigger classification on Doc B
    classify_resp = client.post(f"/api/documents/{security_world.doc_b.id}/classify", headers=rev_a)
    _assert_forbidden(classify_resp, "TENANT_ACCESS_DENIED")

    # Correct classification on Doc B
    patch_resp = client.patch(
        f"/api/documents/{security_world.doc_b.id}/classification",
        json={"category": "hr_documents", "notes": "Cross-tenant tamper attempt"},
        headers=rev_a,
    )
    _assert_forbidden(patch_resp, "TENANT_ACCESS_DENIED")

    # Ensure target document was NOT mutated
    db_session.refresh(security_world.doc_b)
    assert security_world.doc_b.classification == "financial"


# ---------------------------------------------------------------------------
# 2. Structured Extraction Tenant Isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_extraction_access_is_denied(
    client: TestClient, security_world: SecurityWorld, db_session: Session
) -> None:
    """Extracted fields and extraction triggers enforce organization boundaries."""
    rev_a = security_world.headers_for(security_world.reviewer_a)

    # Read extracted fields from Org B document
    get_ext = client.get(f"/api/documents/{security_world.doc_b.id}/extract", headers=rev_a)
    _assert_forbidden(get_ext, "TENANT_ACCESS_DENIED")

    # Trigger extraction on Org B document
    post_ext = client.post(f"/api/documents/{security_world.doc_b.id}/extract", headers=rev_a)
    _assert_forbidden(post_ext, "TENANT_ACCESS_DENIED")

    # Verify DB CRUD helper functions enforce organization_id isolation
    assert get_document_extractions_summary(db_session, security_world.doc_b.id, organization_id=security_world.org_alpha.id) is None
    assert get_extractions_by_document(db_session, security_world.doc_b.id, organization_id=security_world.org_alpha.id) == []
    assert delete_extractions_by_document(db_session, security_world.doc_b.id, organization_id=security_world.org_alpha.id) == 0
    # Accessible to Org B
    assert len(get_extractions_by_document(db_session, security_world.doc_b.id, organization_id=security_world.org_beta.id)) == 1


# ---------------------------------------------------------------------------
# 3. Policy Knowledge Management Tenant Isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_policy_isolation(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """Policies cannot be viewed, modified, or retrieved across tenant boundaries."""
    headers_a = security_world.headers_for(security_world.reviewer_a)
    admin_a = security_world.headers_for(security_world.admin_a)

    # 1. Listing policies in Org A returns only Policy A
    list_resp = client.get("/api/policies", headers=headers_a)
    assert list_resp.status_code == 200
    pols = {p["id"] for p in list_resp.json()}
    assert security_world.policy_a.id in pols
    assert security_world.policy_b.id not in pols

    # 2. Reading Policy B by ID from Org A caller fails (403 or 404)
    get_pol_b = client.get(f"/api/policies/{security_world.policy_b.id}", headers=headers_a)
    assert get_pol_b.status_code in {403, 404}

    # 3. Updating or deleting Policy B by Org A Admin fails (403 or 404)
    put_pol_b = client.put(
        f"/api/policies/{security_world.policy_b.id}",
        json={"name": "Hacked", "domain": "financial", "content": "tampered"},
        headers=admin_a,
    )
    assert put_pol_b.status_code in {403, 404}

    del_pol_b = client.delete(f"/api/policies/{security_world.policy_b.id}", headers=admin_a)
    assert del_pol_b.status_code in {403, 404}

    # 4. Policy vector search from Org A never matches Org B content
    search_resp = client.post(
        "/api/policies/retrieve",
        json={"query": "secret operational expenditure", "document_type": "financial"},
        headers=headers_a,
    )
    if search_resp.status_code == 200:
        matches = search_resp.json().get("matches", [])
        for match in matches:
            assert match.get("policy_id") != security_world.policy_b.id


# ---------------------------------------------------------------------------
# 4. Document Validation Tenant Isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_validation_is_denied(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """Validation requests and validation results are strictly tenant-isolated."""
    rev_a = security_world.headers_for(security_world.reviewer_a)

    # Org A reviewer validates Org B document
    val_post = client.post(f"/api/documents/{security_world.doc_b.id}/validate", headers=rev_a)
    _assert_forbidden(val_post, "TENANT_ACCESS_DENIED")

    # Org A reviewer reads validation results of Org B document
    val_get = client.get(f"/api/documents/{security_world.doc_b.id}/validate", headers=rev_a)
    _assert_forbidden(val_get, "TENANT_ACCESS_DENIED")

    # Org A reviewer runs policy validation on Org B document
    val_pol = client.post(f"/api/documents/{security_world.doc_b.id}/validate-policy", headers=rev_a)
    assert val_pol.status_code in {403, 404}


# ---------------------------------------------------------------------------
# 5. Workflow and Queue Tenant Isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_workflow_queues_and_actions(
    client: TestClient, security_world: SecurityWorld, db_session: Session
) -> None:
    """Review/approval queues, reviewer listings, and approval actions do not cross tenant lines."""
    app_a = security_world.headers_for(security_world.approver_a)
    rev_a = security_world.headers_for(security_world.reviewer_a)

    # 1. Review queue is org-scoped
    rq = client.get("/api/documents/workflow/review-queue", headers=rev_a)
    assert rq.status_code == 200
    for doc in rq.json().get("queue", []):
        assert doc.get("organization_id", security_world.org_alpha.id) == security_world.org_alpha.id

    # 2. Reviewer listing contains only Org A reviewers
    rev_list = client.get("/api/documents/workflow/reviewers", headers=rev_a)
    assert rev_list.status_code == 200
    reviewer_ids = {r["user_id"] for r in rev_list.json()}
    assert security_world.reviewer_a.id in reviewer_ids
    assert security_world.reviewer_b.id not in reviewer_ids

    # 3. Org A Approver cannot approve Org B document
    decide_resp = client.post(
        f"/api/documents/{security_world.doc_b.id}/approve",
        json={"reason": "Cross-tenant approval"},
        headers=app_a,
    )
    assert decide_resp.status_code in {403, 404}

    # 4. Org A Reviewer cannot assign an Org B reviewer to Org A document
    security_world.doc_a1.status = DocumentStatus.SUBMITTED
    db_session.commit()
    assign_resp = client.post(
        f"/api/documents/{security_world.doc_a1.id}/assign",
        json={"reviewer_id": security_world.reviewer_b.id},
        headers=rev_a,
    )
    assert assign_resp.status_code in {403, 422}
    assert assign_resp.json()["error"]["code"] in {"INELIGIBLE_REVIEWER", "WORKFLOW_FORBIDDEN"}


# ---------------------------------------------------------------------------
# 6. Audit Trail and Notification Tenant Isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_audit_and_notification_isolation(
    client: TestClient, security_world: SecurityWorld, db_session: Session
) -> None:
    """Audit logs and notification centers cannot be accessed across tenant boundaries."""
    aud_a = security_world.headers_for(security_world.auditor_a)
    sub_a1 = security_world.headers_for(security_world.submitter_a1)

    # 1. Audit trail of Org B doc is denied to Org A auditor (404 anti-enumeration or 403)
    audit_resp = client.get(f"/api/audit/{security_world.doc_b.id}", headers=aud_a)
    assert audit_resp.status_code in {403, 404}
    if audit_resp.status_code == 403:
        assert audit_resp.json()["error"]["code"] == "TENANT_ACCESS_DENIED"
    else:
        assert audit_resp.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"

    # 2. Audit trail of Submitter A2's doc is denied to Submitter A1
    audit_sub_resp = client.get(f"/api/audit/{security_world.doc_a2.id}", headers=sub_a1)
    _assert_forbidden(audit_sub_resp, "WORKFLOW_FORBIDDEN")

    # 3. Notifications are scoped to caller sub and organization
    notif_b = Notification(
        id="notif_beta_1",
        recipient_user_id=security_world.reviewer_b.id,
        organization_id=security_world.org_beta.id,
        notification_type="ASSIGNED",
        title="Beta alert",
        body="Confidential beta message",
        is_read=False,
    )
    db_session.add(notif_b)
    db_session.commit()

    # Org A reviewer listing notifications does not see Org B notification
    notifs_a = client.get("/api/notifications", headers=security_world.headers_for(security_world.reviewer_a))
    assert notifs_a.status_code == 200
    ids_seen = {n["id"] for n in notifs_a.json().get("items", [])}
    assert notif_b.id not in ids_seen

    # Marking Org B notification as read from Org A fails
    mark_read = client.patch(f"/api/notifications/{notif_b.id}/read", headers=security_world.headers_for(security_world.reviewer_a))
    assert mark_read.status_code in {403, 404}


# ---------------------------------------------------------------------------
# 7. Admin Endpoint Tenant Isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_admin_management_is_forbidden(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """An organization admin in Org A cannot query or modify users or settings in Org B."""
    admin_a = security_world.headers_for(security_world.admin_a)

    # 1. Querying organization details with ?organization_id=org_beta
    org_resp = client.get("/api/admin/organization", params={"organization_id": security_world.org_beta.id}, headers=admin_a)
    _assert_forbidden(org_resp, "ADMIN_TENANT_FORBIDDEN")

    # 2. Querying user list with ?organization_id=org_beta
    users_resp = client.get("/api/admin/users", params={"organization_id": security_world.org_beta.id}, headers=admin_a)
    _assert_forbidden(users_resp, "ADMIN_TENANT_FORBIDDEN")

    # 3. Trying to modify Org B member with organization_id in payload
    modify_resp = client.put(
        f"/api/admin/users/{security_world.submitter_b.id}",
        json={"role": "REVIEWER", "organization_id": security_world.org_beta.id},
        headers=admin_a,
    )
    _assert_forbidden(modify_resp, "ADMIN_TENANT_FORBIDDEN")

    # 4. Modifying Org B member without specifying org fails with 404 (user not found in Org A)
    not_found = client.put(
        f"/api/admin/users/{security_world.submitter_b.id}",
        json={"role": "REVIEWER"},
        headers=admin_a,
    )
    assert not_found.status_code == 404


# ---------------------------------------------------------------------------
# 8. Orphaned Document Fails Closed
# ---------------------------------------------------------------------------


def test_orphaned_document_without_organization_fails_closed(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """A document with organization_id=None or missing metadata cannot be accessed by any tenant."""
    orphan_id = "doc_orphan_999"
    file_path = security_world.storage_dir / f"{orphan_id}.pdf"
    file_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")

    metadata = {
        "document_id": orphan_id,
        "filename": "orphan.pdf",
        "file_type": "application/pdf",
        "status": "EXTRACTED",
        "category": "financial",
        "organization_id": None,
        "submitter_id": security_world.submitter_a1.id,
    }
    (security_world.storage_dir / "metadata" / f"{orphan_id}.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    headers = security_world.headers_for(security_world.reviewer_a)
    assert client.get(f"/api/documents/{orphan_id}", headers=headers).status_code == 403
    assert client.get(f"/api/documents/{orphan_id}/file", headers=headers).status_code == 403
    assert client.get(f"/api/documents/{orphan_id}/extract", headers=headers).status_code == 403
    assert client.post(f"/api/documents/{orphan_id}/classify", headers=headers).status_code == 403
