"""Shared test setup."""
from typing import Optional

import jwt
import pytest
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from api.auth import bearer, get_current_user
from main import app


@pytest.fixture(autouse=True)
def no_real_embedding_calls(monkeypatch):
    """Tests must never reach the embedding provider or the language model (cost, quota, flakiness).

    Without a key those modules fail fast with their service errors. Tests that need vectors
    or answers patch `create_embeddings`, `create_query_embedding(s)` or `chat_json` themselves.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture
def stateless_identity():
    """Resolve the caller from the claims of a self-signed test token, with no database.

    The upload, classification and extraction tests exercise those endpoints, not login. They
    run without a database and mint tokens carrying subject, role, organization, active flag
    and expiry, which is how identity worked before Supabase. Use it with
    `pytestmark = pytest.mark.usefixtures("stateless_identity")`. Permission checks stay real;
    only "who is calling" is taken from the claims. Tests of real authentication must not use it.
    """

    def identity_from_claims(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    ) -> dict:
        def reject(status: int, code: str, message: str) -> HTTPException:
            return HTTPException(status, detail={"code": code, "message": message})

        token = (credentials.credentials or "").strip() if credentials else ""
        if not token:
            raise reject(401, "UNAUTHENTICATED", "A valid bearer token is required.")
        try:
            claims = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": True, "verify_iss": True, "verify_aud": True},
                algorithms=["HS256"],
                issuer="kagaz", audience="kagaz-api",  # the claims the test tokens are minted with
            )
        except jwt.PyJWTError as exc:
            raise reject(401, "UNAUTHENTICATED", "A valid bearer token is required.") from exc
        if not all(str(claims.get(name) or "").strip() for name in ("sub", "role", "organization_id")):
            raise reject(401, "UNAUTHENTICATED", "A valid bearer token is required.")
        if claims.get("active") is False:
            raise reject(403, "ACCOUNT_INACTIVE", "An active user account is required.")
        role = str(claims.get("role") or "")
        return {
            "sub": claims.get("sub"),
            "role": role,
            "organization_id": claims.get("organization_id"),
            "permissions": claims.get("permissions") or [],
            "active": True,
            "memberships": [{"organization_id": claims.get("organization_id"), "role": role}],
        }

    app.dependency_overrides[get_current_user] = identity_from_claims
    yield
    app.dependency_overrides.pop(get_current_user, None)
