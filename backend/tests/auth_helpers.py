"""Test-only stand-in for Supabase Auth.

Production validates the bearer token by asking Supabase, then links the Supabase user to a
Kagaz user by email and resolves organization and role from the database. Tests cannot call
Supabase, so they fake only that one call (`api.auth._supabase_user_from_token`): a test token
carries a Kagaz user id, and the fake answers as Supabase would for that user's email. Everything
after it (membership lookup, organization switching, inactive accounts, permissions) is the real
code under test.
"""
import jwt
import pytest
from fastapi import HTTPException

from app.models.user import User

TEST_TOKEN_SECRET = "test-only-token-secret-at-least-32-bytes"


def create_access_token(*, user_id: str, **_ignored) -> str:
    """A test bearer token for a Kagaz user. Role and organization come from the database, as in production."""
    return jwt.encode({"sub": user_id}, TEST_TOKEN_SECRET, algorithm="HS256")


def install_fake_supabase(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    def fake_supabase_user(raw_token: str) -> dict:
        try:
            user_id = jwt.decode(raw_token, TEST_TOKEN_SECRET, algorithms=["HS256"])["sub"]
        except jwt.PyJWTError as exc:
            raise HTTPException(401, detail={"code": "UNAUTHENTICATED", "message": "A valid bearer token is required."}) from exc
        user = db_session.get(User, user_id)
        email = user.email if user is not None else f"{user_id}@unknown.test"
        return {"id": f"supabase-{user_id}", "email": email, "email_confirmed_at": "2026-01-01T00:00:00Z"}

    monkeypatch.setattr("api.auth._supabase_user_from_token", fake_supabase_user)
