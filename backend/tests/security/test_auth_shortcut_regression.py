"""Development authentication shortcut and bypass regression tests (QA-08 Scope 10 & Section 11).

Proves that development flags (APP_ENV=development), mock tokens, hardcoded test users,
header spoofing, and insecure defaults cannot bypass authentication or RBAC boundaries.
"""
from __future__ import annotations

import base64
import json
import os

import pytest
from fastapi.testclient import TestClient

from api.auth import get_auth_db
from services.password import hash_password, verify_password
from tests.security.conftest import SecurityWorld, create_security_token


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/auth/me"),
        ("GET", "/api/documents"),
        ("POST", "/api/documents"),
        ("GET", "/api/policies"),
        ("GET", "/api/documents/workflow/review-queue"),
        ("GET", "/api/notifications"),
        ("GET", "/api/admin/organization"),
    ],
)
def test_development_environment_does_not_bypass_authentication(
    client: TestClient, security_world: SecurityWorld, monkeypatch: pytest.MonkeyPatch, method: str, path: str
) -> None:
    """Setting APP_ENV=development must NEVER bypass authentication on protected endpoints."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("TESTING", "true")

    # Missing credentials must still return 401
    resp = client.request(method, path)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize(
    "mock_token",
    [
        "kgz_jwt_" + base64.b64encode(json.dumps({"sub": "admin", "role": "SYSTEM_ADMIN"}).encode()).decode(),
        "mock-admin-token",
        "dev-bypass-token-123",
        "Bearer",
        "admin",
        "eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiJ9.",
    ],
)
def test_mock_token_shortcuts_are_completely_rejected(
    client: TestClient, security_world: SecurityWorld, monkeypatch: pytest.MonkeyPatch, mock_token: str
) -> None:
    """Mock-token formats from earlier development phases are rejected unconditionally."""
    monkeypatch.setenv("APP_ENV", "development")
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {mock_token}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_client_headers_cannot_inject_roles_or_permissions(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """Client cannot escalate by passing X-User-Role, X-Role, or X-Permissions headers."""
    headers = security_world.headers_for(security_world.submitter_a1)
    spoofed = {
        **headers,
        "X-User-Role": "ORG_ADMIN",
        "X-Role": "SYSTEM_ADMIN",
        "X-Permissions": "documents:*,policies:*,workflow:*,admin:*",
        "X-Admin": "true",
        "X-Superuser": "true",
    }
    # Submitter remains SUBMITTER; admin endpoints reject with 403
    resp = client.get("/api/admin/users", headers=spoofed)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ADMIN_FORBIDDEN"

    # /api/auth/me reflects the database-authoritative role, ignoring spoofed headers
    me = client.get("/api/auth/me", headers=spoofed)
    assert me.status_code == 200
    assert me.json()["role"] == "SUBMITTER"


def test_unverified_organization_switching_fails_closed(
    client: TestClient, security_world: SecurityWorld
) -> None:
    """A user cannot switch their active tenant to an organization where they have no active membership."""
    headers = security_world.headers_for(security_world.submitter_a1)

    # Attempt to switch to Org Beta where submitter_a1 has NO membership
    resp = client.get(
        "/api/auth/me",
        headers={**headers, "X-Organization-Id": security_world.org_beta.id},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"


def test_missing_supabase_configuration_fails_closed_with_503(
    monkeypatch: pytest.MonkeyPatch, security_world: SecurityWorld
) -> None:
    """When identity provider configuration is missing, the service fails closed with 503."""
    # Temporarily remove fake_supabase override so the real _supabase_user_from_token runs
    from api import auth
    monkeypatch.undo()

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    with pytest.raises(Exception) as exc_info:
        auth._supabase_user_from_token("any-token")
    assert getattr(exc_info.value, "status_code", None) == 503
    assert getattr(exc_info.value, "detail", {}).get("code") == "AUTH_NOT_CONFIGURED"


def test_password_hashing_and_timing_safety_regression() -> None:
    """Verify that password utilities use strong salted hashing and reject malformed inputs."""
    hashed = hash_password("SuperSecretPassphrase!2026")
    assert hashed.startswith("scrypt$")
    assert "SuperSecretPassphrase!2026" not in hashed
    assert hashed != hash_password("SuperSecretPassphrase!2026")  # Salting produces unique hashes

    assert verify_password("SuperSecretPassphrase!2026", hashed) is True
    assert verify_password("WrongPassword", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password("SuperSecretPassphrase!2026", "invalid-hash-string") is False

    with pytest.raises(ValueError):
        hash_password("")
