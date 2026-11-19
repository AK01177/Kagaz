"""File ownership and download security tests (QA-08 Scope 4 & Section 9).

Verifies that file downloads enforce tenant isolation, submitter ownership,
authentication prerequisites, and that file content is never streamed without authorization.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.security.conftest import SecurityWorld, create_security_token


def test_authorized_users_can_download_permitted_files(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """Authorized reviewer, admin, and the owning submitter can download permitted document files."""
    # 1. Owning submitter downloads own document
    sub_headers = security_world.headers_for(security_world.submitter_a1)
    sub_resp = client.get(f"/api/documents/{security_world.doc_a1.id}/file", headers=sub_headers)
    assert sub_resp.status_code == 200
    assert sub_resp.headers["content-type"] == "application/pdf"
    assert b"%PDF" in sub_resp.content

    # 2. Org reviewer downloads document in same org
    rev_headers = security_world.headers_for(security_world.reviewer_a)
    rev_resp = client.get(f"/api/documents/{security_world.doc_a1.id}/file", headers=rev_headers)
    assert rev_resp.status_code == 200
    assert b"%PDF" in rev_resp.content

    # 3. Org admin downloads document in same org
    adm_headers = security_world.headers_for(security_world.admin_a)
    adm_resp = client.get(f"/api/documents/{security_world.doc_a1.id}/file", headers=adm_headers)
    assert adm_resp.status_code == 200
    assert b"%PDF" in adm_resp.content


def test_cross_tenant_file_downloads_are_denied(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """Users cannot download files belonging to another organization, even if they guess the document ID."""
    rev_b = security_world.headers_for(security_world.reviewer_b)

    resp = client.get(f"/api/documents/{security_world.doc_a1.id}/file", headers=rev_b)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "TENANT_ACCESS_DENIED"
    assert b"%PDF" not in resp.content


def test_submitter_cannot_download_other_submitter_files_in_same_org(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """Submitters cannot access or download files uploaded by other submitters in the same tenant."""
    sub_a1 = security_world.headers_for(security_world.submitter_a1)

    # Submitter A1 attempts to download Submitter A2's file
    resp = client.get(f"/api/documents/{security_world.doc_a2.id}/file", headers=sub_a1)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "DOCUMENT_ACCESS_FORBIDDEN"
    assert b"%PDF" not in resp.content


def test_file_download_requires_valid_authentication(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """File downloads reject missing, expired, and forged credentials with 401 before reading file bytes."""
    # 1. Missing credentials
    missing = client.get(f"/api/documents/{security_world.doc_a1.id}/file")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "UNAUTHENTICATED"
    assert b"%PDF" not in missing.content

    # 2. Expired credentials
    expired_token = create_security_token(security_world.submitter_a1.id, exp_delta_seconds=-30)
    expired = client.get(
        f"/api/documents/{security_world.doc_a1.id}/file",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert expired.status_code == 401
    assert b"%PDF" not in expired.content

    # 3. Forged signature
    forged_token = create_security_token(security_world.submitter_a1.id, secret="wrong-secret-key-at-least-32-bytes-long")
    forged = client.get(
        f"/api/documents/{security_world.doc_a1.id}/file",
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert forged.status_code == 401
    assert b"%PDF" not in forged.content


def test_nonexistent_document_file_returns_404(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """Requesting a file for a non-existent document ID returns 404 without leaking internal paths."""
    rev_a = security_world.headers_for(security_world.reviewer_a)
    resp = client.get("/api/documents/doc_nonexistent_99999/file", headers=rev_a)
    assert resp.status_code == 404


@pytest.mark.parametrize(
    "path_traversal_id",
    [
        "../../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "doc/../../shadow",
        "doc_alpha_1/../../../app/core/permissions.py",
    ],
)
def test_path_traversal_attempts_cannot_bypass_file_authorization(
    client: TestClient, security_world: SecurityWorld, path_traversal_id: str
) -> None:
    """Path traversal sequences in document IDs are rejected or safely resolved as not found."""
    rev_a = security_world.headers_for(security_world.reviewer_a)
    resp = client.get(f"/api/documents/{path_traversal_id}/file", headers=rev_a)
    assert resp.status_code in {400, 403, 404, 422}
    assert b"root:" not in resp.content
    assert b"%PDF" not in resp.content
