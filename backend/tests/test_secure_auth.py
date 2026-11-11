"""Tests for secure authentication, password hashing, JWT verification, and server-side RBAC."""
from __future__ import annotations

import base64
import json
import time
import uuid
from typing import Iterator

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import create_access_token, get_auth_db
from app.crud.user import create_user
from app.db.base import Base
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User
from app.schemas.user import UserCreate
from main import app
from services.password import hash_password, verify_password

TEST_JWT_SECRET = "secure-auth-test-secret-key-at-least-32-bytes"


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("JWT_ISSUER", "kagaz")
    monkeypatch.setenv("JWT_AUDIENCE", "kagaz-api")


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


def _seed_identity_graph(db: Session) -> dict:
    org_a = Organization(id="org_auth_a", name="Auth Alpha", slug="auth-alpha", is_active=True)
    org_b = Organization(id="org_auth_b", name="Auth Beta", slug="auth-beta", is_active=True)
    org_inactive = Organization(id="org_inactive", name="Inactive Org", slug="inactive-org", is_active=False)
    db.add_all([org_a, org_b, org_inactive])
    db.flush()

    submitter = create_user(
        db,
        UserCreate(
            id="usr_sub_auth",
            email="Submitter@Alpha.test",
            full_name="Alice Submitter",
            password="CorrectHorseBatteryStaple!9",
            is_active=True,
        ),
    )
    reviewer = create_user(
        db,
        UserCreate(
            id="usr_rev_auth",
            email="reviewer@alpha.test",
            full_name="Bob Reviewer",
            password="ReviewerSecretPassword!7",
            is_active=True,
        ),
    )
    inactive_user = User(
        id="usr_inactive_auth",
        email="disabled@alpha.test",
        full_name="Disabled User",
        password_hash=hash_password("DisabledPass!1"),
        is_active=False,
    )
    no_membership_user = User(
        id="usr_nomem_auth",
        email="orphan@alpha.test",
        full_name="Orphan User",
        password_hash=hash_password("OrphanPass!1"),
        is_active=True,
    )
    sso_only_user = User(
        id="usr_sso_only",
        email="sso@alpha.test",
        full_name="SSO Only",
        password_hash=None,
        is_active=True,
    )
    other_org_user = create_user(
        db,
        UserCreate(
            id="usr_beta_auth",
            email="user@beta.test",
            full_name="Beta User",
            password="BetaUserPassword!4",
            is_active=True,
        ),
    )
    db.add_all([inactive_user, no_membership_user, sso_only_user])
    db.flush()

    m_sub = Membership(
        organization_id=org_a.id,
        user_id=submitter.id,
        role=MembershipRole.SUBMITTER,
        is_active=True,
    )
    m_rev = Membership(
        organization_id=org_a.id,
        user_id=reviewer.id,
        role=MembershipRole.REVIEWER,
        is_active=True,
    )
    m_inact = Membership(
        organization_id=org_a.id,
        user_id=inactive_user.id,
        role=MembershipRole.SUBMITTER,
        is_active=True,
    )
    m_org_inact = Membership(
        organization_id=org_inactive.id,
        user_id=no_membership_user.id,
        role=MembershipRole.SUBMITTER,
        is_active=True,
    )
    m_beta = Membership(
        organization_id=org_b.id,
        user_id=other_org_user.id,
        role=MembershipRole.REVIEWER,
        is_active=True,
    )
    doc = Document(
        id="doc_auth_1",
        organization_id=org_a.id,
        uploaded_by=submitter.id,
        filename="invoice.pdf",
        file_type="application/pdf",
        file_size=128,
        storage_path="doc_auth_1.pdf",
        status=DocumentStatus.CLASSIFIED,
    )
    db.add_all([m_sub, m_rev, m_inact, m_org_inact, m_beta, doc])
    db.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "submitter": submitter,
        "reviewer": reviewer,
        "other_org_user": other_org_user,
        "m_rev": m_rev,
        "doc": doc,
    }


def test_password_hashing_and_constant_time_verification() -> None:
    hashed = hash_password("TopSecretPass!42")
    assert hashed.startswith("scrypt$")
    assert "TopSecretPass!42" not in hashed
    assert hashed != hash_password("TopSecretPass!42")
    assert verify_password("TopSecretPass!42", hashed) is True
    assert verify_password("WrongPass", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password("TopSecretPass!42", "not-a-valid-hash") is False
    with pytest.raises(ValueError):
        hash_password("")


def test_login_verifies_registered_credentials_and_ignores_caller_claims(
    client: TestClient, db_session: Session
) -> None:
    seeded = _seed_identity_graph(db_session)

    # Password is stored salted-hashed, never plaintext
    assert seeded["submitter"].password_hash is not None
    assert seeded["submitter"].password_hash.startswith("scrypt$")

    # Valid registered credentials succeed and resolve role/org server-side
    resp = client.post(
        "/api/auth/login",
        json={
            "email": "submitter@alpha.test",
            "password": "CorrectHorseBatteryStaple!9",
            "role": "ORG_ADMIN",  # Caller-supplied escalation must be ignored
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["user_id"] == seeded["submitter"].id
    assert body["user"]["role"] == "SUBMITTER"
    assert body["user"]["organization_id"] == seeded["org_a"].id

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["user_id"] == seeded["submitter"].id
    assert me.json()["role"] == "SUBMITTER"
    assert me.json()["organization_id"] == seeded["org_a"].id

    # Attempting to log into an organization the user is not a member of fails closed
    cross_org = client.post(
        "/api/auth/login",
        json={
            "email": "submitter@alpha.test",
            "password": "CorrectHorseBatteryStaple!9",
            "organization_id": seeded["org_b"].id,
        },
    )
    assert cross_org.status_code == 403


@pytest.mark.parametrize(
    "payload,expected_status",
    [
        ({"email": "submitter@alpha.test", "password": "wrong-password"}, 401),
        ({"email": "unknown@alpha.test", "password": "CorrectHorseBatteryStaple!9"}, 401),
        ({"email": "submitter@alpha.test", "password": ""}, 401),
        ({"email": "sso@alpha.test", "password": "any-password"}, 401),
        ({"email": "disabled@alpha.test", "password": "DisabledPass!1"}, 403),
        ({"email": "orphan@alpha.test", "password": "OrphanPass!1"}, 403),
    ],
)
def test_login_rejects_invalid_or_inactive_credentials(
    client: TestClient, db_session: Session, payload: dict, expected_status: int
) -> None:
    _seed_identity_graph(db_session)
    resp = client.post("/api/auth/login", json=payload)
    assert resp.status_code == expected_status
    assert "access_token" not in resp.json()


def test_login_fails_closed_when_database_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_auth_db] = lambda: None
    try:
        with TestClient(app) as tc:
            resp = tc.post(
                "/api/auth/login",
                json={"email": "anyone@alpha.test", "password": "secret"},
            )
            assert resp.status_code == 503
    finally:
        app.dependency_overrides.pop(get_auth_db, None)


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/auth/me"),
        ("POST", "/api/documents"),
        ("GET", "/api/documents/doc_auth_1"),
        ("GET", "/api/documents/doc_auth_1/file"),
        ("POST", "/api/documents/doc_auth_1/classify"),
        ("PATCH", "/api/documents/doc_auth_1/classification"),
        ("GET", "/api/documents/doc_auth_1/extract"),
        ("POST", "/api/documents/doc_auth_1/extract"),
        ("POST", "/api/documents/doc_auth_1/validate"),
        ("GET", "/api/documents/doc_auth_1/validate"),
        ("GET", "/api/policies"),
        ("GET", "/api/documents/workflow/review-queue"),
        ("GET", "/api/notifications"),
        ("GET", "/api/audit/doc_auth_1"),
    ],
)
def test_missing_or_mock_credentials_return_401_even_in_development_env(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
) -> None:
    _seed_identity_graph(db_session)
    monkeypatch.setenv("APP_ENV", "development")

    mock_payload = base64.b64encode(
        json.dumps(
            {
                "sub": "usr_rev_auth",
                "email": "admin@alpha.test",
                "role": "ORG_ADMIN",
                "organization_id": "org_auth_a",
                "active": True,
            }
        ).encode("utf-8")
    ).decode("ascii")
    mock_token = f"kgz_jwt_{mock_payload}"

    for headers in (
        {},
        {"Authorization": ""},
        {"Authorization": "Bearer undefined"},
        {"Authorization": "Bearer null"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": f"Bearer {mock_token}"},
    ):
        resp = client.request(method, path, headers=headers)
        assert resp.status_code == 401, f"{method} {path} with {headers} returned {resp.status_code}"


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda: "not-even-a-jwt",
        lambda: "a.b.c",
        lambda: jwt.encode(
            {
                "sub": "usr_sub_auth",
                "role": "SUBMITTER",
                "organization_id": "org_auth_a",
                "active": True,
                "iss": "kagaz",
                "aud": "kagaz-api",
                "iat": int(time.time()) - 600,
                "exp": int(time.time()) - 10,
            },
            TEST_JWT_SECRET,
            algorithm="HS256",
        ),
        lambda: jwt.encode(
            {
                "sub": "usr_sub_auth",
                "role": "SUBMITTER",
                "organization_id": "org_auth_a",
                "active": True,
                "iss": "wrong-issuer",
                "aud": "kagaz-api",
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
            },
            TEST_JWT_SECRET,
            algorithm="HS256",
        ),
        lambda: jwt.encode(
            {
                "sub": "usr_sub_auth",
                "role": "SUBMITTER",
                "organization_id": "org_auth_a",
                "active": True,
                "iss": "kagaz",
                "aud": "kagaz-api",
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
            },
            "forged-secret-that-must-always-be-rejected-32b",
            algorithm="HS256",
        ),
        lambda: jwt.encode(
            {
                "sub": "usr_unregistered_999",
                "role": "ORG_ADMIN",
                "organization_id": "org_auth_a",
                "active": True,
                "iss": "kagaz",
                "aud": "kagaz-api",
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
            },
            TEST_JWT_SECRET,
            algorithm="HS256",
        ),
    ],
)
def test_expired_malformed_and_unregistered_tokens_are_rejected(
    client: TestClient, db_session: Session, token_factory
) -> None:
    _seed_identity_graph(db_session)
    token = token_factory()
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_server_side_membership_role_overrides_stale_token_claims(
    client: TestClient, db_session: Session
) -> None:
    seeded = _seed_identity_graph(db_session)
    reviewer_token = create_access_token(
        user_id=seeded["reviewer"].id,
        role="REVIEWER",
        organization_id=seeded["org_a"].id,
    )

    # Initially REVIEWER has access to reviewer endpoints
    assert (
        client.get(
            "/api/documents/workflow/review-queue",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        ).status_code
        == 200
    )

    # Admin demotes user in database while old REVIEWER JWT is still unexpired
    seeded["m_rev"].role = MembershipRole.SUBMITTER
    db_session.commit()

    # /api/auth/me reflects authoritative DB role, and reviewer endpoint rejects stale token
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {reviewer_token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "SUBMITTER"

    rev_req = client.get(
        "/api/documents/workflow/review-queue",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert rev_req.status_code == 403

    # Deactivating membership revokes access immediately
    seeded["m_rev"].is_active = False
    db_session.commit()
    assert (
        client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        ).status_code
        == 403
    )


def test_cross_organization_document_access_is_forbidden(
    client: TestClient, db_session: Session
) -> None:
    seeded = _seed_identity_graph(db_session)
    beta_token = create_access_token(
        user_id=seeded["other_org_user"].id,
        role="REVIEWER",
        organization_id=seeded["org_b"].id,
    )
    resp = client.get(
        f"/api/documents/{seeded['doc'].id}",
        headers={"Authorization": f"Bearer {beta_token}"},
    )
    assert resp.status_code == 403


def test_missing_or_short_jwt_secret_fails_closed(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_identity_graph(db_session)
    monkeypatch.setenv("JWT_SECRET", "too-short")
    with pytest.raises(RuntimeError):
        create_access_token("usr_sub_auth", "SUBMITTER", "org_auth_a")

    login_resp = client.post(
        "/api/auth/login",
        json={"email": "submitter@alpha.test", "password": "CorrectHorseBatteryStaple!9"},
    )
    assert login_resp.status_code == 503
    assert client.get("/api/health").status_code == 200
