"""Authentication and token verification security tests (QA-08 Scope 1).

Tests valid, invalid, expired, missing tokens, unconfirmed emails, inactive users,
unregistered users, membership checks, multi-organization switching, and database failure handling.
"""
from __future__ import annotations

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.auth import get_auth_db
from main import app
from tests.security.conftest import (
    SECURITY_TOKEN_SECRET,
    SecurityWorld,
    create_security_token,
)


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/auth/me"),
        ("GET", "/api/auth/memberships"),
        ("GET", "/api/documents"),
        ("POST", "/api/documents"),
        ("GET", "/api/policies"),
        ("GET", "/api/documents/workflow/review-queue"),
        ("GET", "/api/documents/workflow/approval-queue"),
        ("GET", "/api/notifications"),
        ("GET", "/api/admin/organization"),
        ("GET", "/api/admin/users"),
    ],
)
def test_protected_endpoints_reject_missing_credentials(
    client: TestClient, security_world: SecurityWorld, method: str, path: str
) -> None:
    """Every protected endpoint must return 401 when no authorization credentials are provided."""
    resp = client.request(method, path)
    assert resp.status_code == 401, f"{method} {path} returned {resp.status_code}"
    body = resp.json()
    assert body["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize(
    "auth_header",
    [
        "",
        "   ",
        "Bearer",
        "Bearer ",
        "Bearer undefined",
        "Bearer null",
        "Basic dXNlcjpwYXNz",
        "Token some-api-key",
        "Digest username=foo",
    ],
)
def test_protected_endpoints_reject_malformed_auth_headers(
    client: TestClient, security_world: SecurityWorld, auth_header: str
) -> None:
    """Headers that omit Bearer, use other schemes, or provide undefined/null tokens return 401."""
    resp = client.get("/api/auth/me", headers={"Authorization": auth_header})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize(
    "invalid_token",
    [
        "not-a-valid-jwt",
        "header.payload",
        "header.payload.signature.extra",
        "eyJh.eyJi.eyJj",
    ],
)
def test_token_validation_rejects_corrupted_tokens(
    client: TestClient, security_world: SecurityWorld, invalid_token: str
) -> None:
    """Corrupted and malformed token formats must be rejected with 401."""
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {invalid_token}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_token_validation_rejects_expired_tokens(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """Expired tokens must fail authentication immediately."""
    expired_token = create_security_token(
        security_world.submitter_a1.id,
        exp_delta_seconds=-60,
    )
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_token_validation_rejects_forged_signature(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """Tokens signed with a different key must be rejected with 401."""
    forged_token = create_security_token(
        security_world.submitter_a1.id,
        secret="attacker-forged-secret-key-32-bytes-long",
    )
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_unconfirmed_email_is_rejected_with_403(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """A user who has not confirmed their email address cannot access protected endpoints."""
    token = create_security_token(
        security_world.submitter_a1.id,
        unconfirmed=True,
    )
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "EMAIL_NOT_CONFIRMED"


def test_unregistered_user_token_is_rejected_with_403(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """A valid token for a user not registered in Kagaz fails closed."""
    unregistered_token = create_security_token("usr_nonexistent_99999")
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {unregistered_token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"


def test_inactive_user_account_is_rejected_with_403(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """An account marked is_active=False cannot authenticate."""
    token = create_security_token(security_world.inactive_user_a.id)
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCOUNT_INACTIVE"


def test_user_with_no_memberships_is_rejected_with_403(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """An active user without any organization memberships is rejected."""
    token = create_security_token(security_world.orphan_user.id)
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"


def test_user_with_inactive_membership_is_rejected_with_403(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """A user whose membership is is_active=False cannot authenticate."""
    token = create_security_token(security_world.inactive_member_a.id)
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"


def test_user_in_inactive_organization_is_rejected_with_403(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """A user whose organization is is_active=False cannot authenticate."""
    token = create_security_token(security_world.inactive_org_user.id)
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"


def test_valid_authenticated_user_profile_and_memberships(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """A valid authenticated user resolves profile, active org, role, and permissions from DB."""
    headers = security_world.headers_for(security_world.reviewer_a)
    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me = me_resp.json()
    assert me["user_id"] == security_world.reviewer_a.id
    assert me["email"] == security_world.reviewer_a.email
    assert me["role"] == "REVIEWER"
    assert me["organization_id"] == security_world.org_alpha.id
    assert me["active"] is True

    mem_resp = client.get("/api/auth/memberships", headers=headers)
    assert mem_resp.status_code == 200
    mems = mem_resp.json()
    assert mems["user_id"] == security_world.reviewer_a.id
    assert mems["active_organization_id"] == security_world.org_alpha.id
    assert len(mems["memberships"]) >= 1


def test_multi_organization_context_resolution_and_switching(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """A multi-org user defaults to earliest membership and can switch via X-Organization-Id."""
    user = security_world.multi_user

    # 1. Default context: Org Alpha -> SUBMITTER
    default_resp = client.get("/api/auth/me", headers=security_world.headers_for(user))
    assert default_resp.status_code == 200
    assert default_resp.json()["organization_id"] == security_world.org_alpha.id
    assert default_resp.json()["role"] == "SUBMITTER"

    # 2. Switch to Org Beta via X-Organization-Id -> REVIEWER
    beta_resp = client.get(
        "/api/auth/me",
        headers=security_world.headers_for(user, org_id=security_world.org_beta.id),
    )
    assert beta_resp.status_code == 200
    assert beta_resp.json()["organization_id"] == security_world.org_beta.id
    assert beta_resp.json()["role"] == "REVIEWER"

    # 3. Switching into unauthorized organization returns 403
    unauth_resp = client.get(
        "/api/auth/me",
        headers=security_world.headers_for(user, org_id="org_unauthorized_999"),
    )
    assert unauth_resp.status_code == 403
    assert unauth_resp.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"

    # 4. Empty or whitespace X-Organization-Id returns 403
    empty_resp = client.get(
        "/api/auth/me",
        headers=security_world.headers_for(user, org_id="   "),
    )
    assert empty_resp.status_code == 403
    assert empty_resp.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"


def test_database_outage_fails_closed_with_503(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """When the identity database is unavailable, get_current_user fails closed with 503."""
    app.dependency_overrides[get_auth_db] = lambda: None
    try:
        resp = client.get(
            "/api/auth/me",
            headers=security_world.headers_for(security_world.submitter_a1),
        )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "AUTH_DATABASE_UNAVAILABLE"
    finally:
        app.dependency_overrides[get_auth_db] = lambda: security_world.db
