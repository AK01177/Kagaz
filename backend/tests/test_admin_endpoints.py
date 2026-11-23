"""Organization / member administration and same-org document privacy."""
from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User
from main import app
from tests.auth_helpers import create_access_token, install_fake_supabase


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fks(conn, _rec):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _fake_supabase(monkeypatch, db_session):
    install_fake_supabase(monkeypatch, db_session)


@pytest.fixture()
def client(db_session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


ORG = "org_acme"


def _header(user_id: str, role: str, org: str = ORG) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id=user_id, role=role, organization_id=org)}"}


@pytest.fixture()
def world(db_session):
    db_session.add(Organization(id=ORG, name="Acme", slug="acme", is_active=True))
    people = {
        "sysadmin": MembershipRole.SYSTEM_ADMIN, "orgadmin": MembershipRole.ORG_ADMIN,
        "sub1": MembershipRole.SUBMITTER, "sub2": MembershipRole.SUBMITTER,
    }
    for uid, role in people.items():
        db_session.add(User(id=uid, email=f"{uid}@acme.test", full_name=uid, is_active=True))
        db_session.add(Membership(organization_id=ORG, user_id=uid, role=role, is_active=True))
    db_session.add(Document(
        id="doc_sub1", organization_id=ORG, uploaded_by="sub1", filename="a.pdf",
        file_type="application/pdf", file_size=1, storage_path="a.pdf", status=DocumentStatus.EXTRACTED,
    ))
    db_session.commit()


def test_system_admin_creates_org_with_first_admin(client, world, db_session):
    res = client.post("/api/admin/organizations", headers=_header("sysadmin", "SYSTEM_ADMIN"),
                      json={"name": "Gamma Ltd", "admin_email": "Priya@Gamma.test"})
    assert res.status_code == 201, res.text
    assert res.json()["slug"] == "gamma-ltd" and res.json()["active_member_count"] == 1
    user = db_session.query(User).filter(User.email == "priya@gamma.test").one()
    member = db_session.query(Membership).filter(Membership.user_id == user.id).one()
    assert member.role == MembershipRole.ORG_ADMIN
    # same name again gets a unique slug
    again = client.post("/api/admin/organizations", headers=_header("sysadmin", "SYSTEM_ADMIN"),
                        json={"name": "Gamma Ltd", "admin_email": "other@gamma.test"})
    assert again.json()["slug"] == "gamma-ltd-2"
    listed = client.get("/api/admin/organizations", headers=_header("sysadmin", "SYSTEM_ADMIN"))
    assert {o["name"] for o in listed.json()["organizations"]} == {"Acme", "Gamma Ltd"}


def test_org_admin_cannot_manage_organizations(client, world):
    h = _header("orgadmin", "ORG_ADMIN")
    assert client.get("/api/admin/organizations", headers=h).status_code == 403
    assert client.post("/api/admin/organizations", headers=h,
                       json={"name": "Nope", "admin_email": "x@y.test"}).status_code == 403


def test_org_admin_adds_members(client, world):
    h = _header("orgadmin", "ORG_ADMIN")
    res = client.post("/api/admin/users", headers=h, json={"email": "ravi@acme.test", "role": "REVIEWER"})
    assert res.status_code == 201 and res.json()["role"] == "REVIEWER"
    assert client.post("/api/admin/users", headers=h,
                       json={"email": "RAVI@acme.test", "role": "REVIEWER"}).status_code == 409
    assert client.post("/api/admin/users", headers=h,
                       json={"email": "not-an-email", "role": "REVIEWER"}).status_code == 422
    assert client.post("/api/admin/users", headers=h,
                       json={"email": "boss@acme.test", "role": "SYSTEM_ADMIN"}).status_code == 403
    users = client.get("/api/admin/users", headers=h).json()["users"]
    assert "ravi@acme.test" in {u["email"] for u in users}


def test_non_admins_cannot_add_members(client, world):
    assert client.post("/api/admin/users", headers=_header("sub1", "SUBMITTER"),
                       json={"email": "z@acme.test", "role": "REVIEWER"}).status_code == 403


def test_existing_person_in_another_org_gets_second_membership(client, world, db_session):
    db_session.add(Organization(id="org_beta", name="Beta", slug="beta", is_active=True))
    db_session.commit()
    res = client.post("/api/admin/users", headers=_header("orgadmin", "ORG_ADMIN"),
                      json={"email": "sub1@acme.test", "role": "REVIEWER"})  # sub1 already in Acme -> 409
    assert res.status_code == 409
    client.post("/api/admin/organizations", headers=_header("sysadmin", "SYSTEM_ADMIN"),
                json={"name": "Delta", "admin_email": "sub1@acme.test"})
    assert db_session.query(Membership).filter(Membership.user_id == "sub1").count() == 2
    assert db_session.query(User).filter(User.email == "sub1@acme.test").count() == 1


def test_memberships_include_organization_name(client, world):
    res = client.get("/api/auth/memberships", headers=_header("sub1", "SUBMITTER"))
    assert res.json()["memberships"][0]["organization_name"] == "Acme"


def test_submitter_cannot_see_another_submitters_document(client, world):
    owner, other = _header("sub1", "SUBMITTER"), _header("sub2", "SUBMITTER")
    assert [d["id"] for d in client.get("/api/documents", headers=owner).json()["documents"]] == ["doc_sub1"]
    assert client.get("/api/documents", headers=other).json()["documents"] == []
    assert client.get("/api/documents/doc_sub1", headers=other).status_code in (403, 404)


def test_org_admin_cannot_read_documents(client, world):
    h = _header("orgadmin", "ORG_ADMIN")
    assert client.get("/api/documents", headers=h).status_code == 403
    assert client.get("/api/documents/doc_sub1", headers=h).status_code == 403


# --- self-service sign-up: a signed-in person with no workspace creates their own organization ---

def test_new_person_creates_own_organization_and_becomes_admin(client, world, db_session):
    h = _header("newbie", "SUBMITTER", org="none")  # Supabase account exists, no Kagaz profile yet
    assert client.get("/api/auth/me", headers=h).status_code == 403  # the "ask an administrator" situation

    res = client.post("/api/auth/organizations", headers=h, json={"name": "Newco"})
    assert res.status_code == 201, res.text
    assert res.json()["organization_name"] == "Newco" and res.json()["role"] == "ORG_ADMIN"

    me = client.get("/api/auth/me", headers=h).json()
    assert me["role"] == "ORG_ADMIN" and me["organization_id"] == res.json()["organization_id"]
    names = [m["organization_name"] for m in client.get("/api/auth/memberships", headers=h).json()["memberships"]]
    assert names == ["Newco"]


def test_self_service_is_only_for_people_without_a_workspace(client, world):
    again = client.post("/api/auth/organizations", headers=_header("sub1", "SUBMITTER"), json={"name": "Second Org"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "ALREADY_HAS_WORKSPACE"

    h = _header("newbie2", "SUBMITTER", org="none")
    assert client.post("/api/auth/organizations", headers=h, json={"name": "First"}).status_code == 201
    assert client.post("/api/auth/organizations", headers=h, json={"name": "Another"}).status_code == 409


def test_self_service_validates_input_and_needs_a_token(client, world):
    assert client.post("/api/auth/organizations", json={"name": "Nope Inc"}).status_code == 401
    assert client.post("/api/auth/organizations", headers=_header("newbie3", "SUBMITTER", org="none"),
                       json={"name": "x"}).status_code == 422


def test_existing_profile_without_membership_is_linked(client, world, db_session):
    db_session.add(User(id="orphan", email="orphan@acme.test", full_name="Orphan", is_active=True))
    db_session.commit()
    res = client.post("/api/auth/organizations", headers=_header("orphan", "SUBMITTER", org="none"),
                      json={"name": "Orphan Works"})
    assert res.status_code == 201
    assert db_session.query(User).filter(User.email == "orphan@acme.test").count() == 1


def test_same_name_gets_unique_slug(client, world, db_session):
    for uid in ("p1", "p2"):
        assert client.post("/api/auth/organizations", headers=_header(uid, "SUBMITTER", org="none"),
                           json={"name": "Twin Co"}).status_code == 201
    slugs = sorted(o.slug for o in db_session.query(Organization).filter(Organization.name == "Twin Co"))
    assert slugs == ["twin-co", "twin-co-2"]
