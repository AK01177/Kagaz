"""Reusable security testing framework fixtures, multi-tenant world setup, and fake Supabase provider.

Designed for QA-08: Authentication, RBAC, and Tenant Isolation testing.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Iterator, Mapping

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import get_auth_db
from app.crud.extraction import create_extractions_bulk
from app.crud.user import create_user
from app.crud.validation import save_validation_result
from app.db.base import Base
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.policy import Policy, PolicyVersion, PolicyVersionStatus
from app.models.user import User
from app.models.workflow import AuditEvent
from app.schemas.extraction import ExtractionCreate
from app.schemas.user import UserCreate
from main import app
from storage.document_storage import DocumentStorage

SECURITY_TOKEN_SECRET = "qa08-security-test-token-secret-at-least-32-bytes"


def make_valid_pdf_bytes(text: str = "QA-08 Test PDF Content") -> bytes:
    """Generate a valid, single-page, readable PDF in memory."""
    import io
    from reportlab.pdfgen import canvas

    stream = io.BytesIO()
    pdf_canvas = canvas.Canvas(stream)
    pdf_canvas.drawString(72, 780, text)
    pdf_canvas.save()
    return stream.getvalue()


@pytest.fixture(autouse=True)
def security_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Set standard security test environment variables and isolated document storage."""
    storage_dir = tmp_path / "document_storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "metadata").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("JWT_SECRET", SECURITY_TOKEN_SECRET)
    monkeypatch.setenv("JWT_ISSUER", "kagaz")
    monkeypatch.setenv("JWT_AUDIENCE", "kagaz-api")
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return storage_dir


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """Provide an isolated, transactional in-memory SQLite database for security tests."""
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


def create_security_token(
    user_id: str,
    *,
    secret: str = SECURITY_TOKEN_SECRET,
    algorithm: str = "HS256",
    exp_delta_seconds: int = 3600,
    unconfirmed: bool = False,
    email: str | None = None,
    extra_claims: Mapping[str, Any] | None = None,
) -> str:
    """Generate a signed test JWT for the fake Supabase authentication provider."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": now,
        "exp": now + exp_delta_seconds,
    }
    if email is not None:
        payload["email"] = email
    if unconfirmed:
        payload["unconfirmed"] = True
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture(autouse=True)
def fake_supabase(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> None:
    """Mock only the external Supabase user verification call (`api.auth._supabase_user_from_token`).

    All internal token claims verification, Kagaz user resolution, DB membership lookups,
    active organization selection, and RBAC matrix evaluations run the real code under test.
    """
    def _fake_supabase_user_from_token(raw_token: str) -> dict:
        if not raw_token or raw_token in ("undefined", "null", ""):
            raise HTTPException(
                status_code=401,
                detail={"code": "UNAUTHENTICATED", "message": "A valid bearer token is required."},
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            claims = jwt.decode(
                raw_token,
                SECURITY_TOKEN_SECRET,
                algorithms=["HS256"],
            )
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(
                status_code=401,
                detail={"code": "UNAUTHENTICATED", "message": "A valid bearer token is required."},
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=401,
                detail={"code": "UNAUTHENTICATED", "message": "A valid bearer token is required."},
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        user_id = str(claims.get("sub") or "")
        user = db_session.get(User, user_id)
        email = str(claims.get("email") or (user.email if user else f"{user_id}@test.kagaz.local"))

        email_confirmed_at = None if claims.get("unconfirmed") else "2026-01-01T00:00:00Z"
        return {
            "id": f"supabase-{user_id}",
            "email": email,
            "email_confirmed_at": email_confirmed_at,
            "user_metadata": claims.get("user_metadata", {}),
        }

    monkeypatch.setattr("api.auth._supabase_user_from_token", _fake_supabase_user_from_token)


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    """TestClient configured with security test DB session overrides."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_auth_db] = lambda: db_session
    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_auth_db, None)


class SecurityWorld:
    """Pre-seeded multi-organization test environment with full role-permission coverage."""

    def __init__(self, db: Session, storage_dir: Path) -> None:
        self.db = db
        self.storage_dir = storage_dir

        # 1. Organizations
        self.org_alpha = Organization(id="org_alpha", name="Alpha Corp", slug="alpha-corp", is_active=True)
        self.org_beta = Organization(id="org_beta", name="Beta LLC", slug="beta-llc", is_active=True)
        self.org_inactive = Organization(id="org_inactive", name="Inactive Org", slug="inactive-org", is_active=False)
        self.db.add_all([self.org_alpha, self.org_beta, self.org_inactive])
        self.db.flush()

        # 2. Users and Memberships
        # Org Alpha Members
        self.submitter_a1 = self._add_user("usr_sub_a1", "sub_a1@alpha.test", "Alice Submitter 1")
        self.submitter_a2 = self._add_user("usr_sub_a2", "sub_a2@alpha.test", "Adam Submitter 2")
        self.reviewer_a = self._add_user("usr_rev_a", "rev_a@alpha.test", "Bob Reviewer")
        self.approver_a = self._add_user("usr_app_a", "app_a@alpha.test", "Charlie Approver")
        self.compliance_a = self._add_user("usr_comp_a", "comp_a@alpha.test", "Dana Compliance")
        self.auditor_a = self._add_user("usr_aud_a", "aud_a@alpha.test", "Eve Auditor")
        self.admin_a = self._add_user("usr_adm_a", "adm_a@alpha.test", "Frank Admin")
        self.sys_admin = self._add_user("usr_sys_admin", "sysadmin@alpha.test", "Grace System Admin")

        # Inactive user / Inactive membership / Inactive org users
        self.inactive_user_a = self._add_user("usr_inact_user", "disabled@alpha.test", "Disabled User", is_active=False)
        self.inactive_member_a = self._add_user("usr_inact_mem", "inactive_mem@alpha.test", "Inactive Member User")
        self.orphan_user = self._add_user("usr_orphan", "orphan@alpha.test", "Orphan User")
        self.inactive_org_user = self._add_user("usr_inact_org", "inact_org@alpha.test", "Inactive Org User")

        # Org Beta Members
        self.submitter_b = self._add_user("usr_sub_b", "sub_b@beta.test", "Brenda Submitter B")
        self.reviewer_b = self._add_user("usr_rev_b", "rev_b@beta.test", "Brian Reviewer B")
        self.approver_b = self._add_user("usr_app_b", "app_b@beta.test", "Betty Approver B")
        self.admin_b = self._add_user("usr_adm_b", "adm_b@beta.test", "Ben Admin B")

        # Multi-org User
        self.multi_user = self._add_user("usr_multi", "multi@shared.test", "Morgan Multi")

        # Memberships
        memberships = [
            # Alpha active
            Membership(id="mem_sub_a1", user_id=self.submitter_a1.id, organization_id=self.org_alpha.id, role=MembershipRole.SUBMITTER, is_active=True),
            Membership(id="mem_sub_a2", user_id=self.submitter_a2.id, organization_id=self.org_alpha.id, role=MembershipRole.SUBMITTER, is_active=True),
            Membership(id="mem_rev_a", user_id=self.reviewer_a.id, organization_id=self.org_alpha.id, role=MembershipRole.REVIEWER, is_active=True),
            Membership(id="mem_app_a", user_id=self.approver_a.id, organization_id=self.org_alpha.id, role=MembershipRole.APPROVER, is_active=True),
            Membership(id="mem_comp_a", user_id=self.compliance_a.id, organization_id=self.org_alpha.id, role=MembershipRole.COMPLIANCE, is_active=True),
            Membership(id="mem_aud_a", user_id=self.auditor_a.id, organization_id=self.org_alpha.id, role=MembershipRole.AUDITOR, is_active=True),
            Membership(id="mem_adm_a", user_id=self.admin_a.id, organization_id=self.org_alpha.id, role=MembershipRole.ORG_ADMIN, is_active=True),
            Membership(id="mem_sys_a", user_id=self.sys_admin.id, organization_id=self.org_alpha.id, role=MembershipRole.SYSTEM_ADMIN, is_active=True),
            # Alpha inactive user membership
            Membership(id="mem_inact_u", user_id=self.inactive_user_a.id, organization_id=self.org_alpha.id, role=MembershipRole.SUBMITTER, is_active=True),
            # Alpha user with inactive membership
            Membership(id="mem_inact_m", user_id=self.inactive_member_a.id, organization_id=self.org_alpha.id, role=MembershipRole.SUBMITTER, is_active=False),
            # Inactive org membership
            Membership(id="mem_inact_org", user_id=self.inactive_org_user.id, organization_id=self.org_inactive.id, role=MembershipRole.SUBMITTER, is_active=True),
            # Beta active
            Membership(id="mem_sub_b", user_id=self.submitter_b.id, organization_id=self.org_beta.id, role=MembershipRole.SUBMITTER, is_active=True),
            Membership(id="mem_rev_b", user_id=self.reviewer_b.id, organization_id=self.org_beta.id, role=MembershipRole.REVIEWER, is_active=True),
            Membership(id="mem_app_b", user_id=self.approver_b.id, organization_id=self.org_beta.id, role=MembershipRole.APPROVER, is_active=True),
            Membership(id="mem_adm_b", user_id=self.admin_b.id, organization_id=self.org_beta.id, role=MembershipRole.ORG_ADMIN, is_active=True),
            # Multi-tenant user: Alpha earliest (SUBMITTER), Beta later (REVIEWER)
            Membership(id="mem_multi_a", user_id=self.multi_user.id, organization_id=self.org_alpha.id, role=MembershipRole.SUBMITTER, is_active=True, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
            Membership(id="mem_multi_b", user_id=self.multi_user.id, organization_id=self.org_beta.id, role=MembershipRole.REVIEWER, is_active=True, created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        ]
        self.db.add_all(memberships)
        self.db.flush()

        # 3. Documents
        self.doc_a1 = self._add_document(
            doc_id="doc_alpha_1",
            org_id=self.org_alpha.id,
            uploaded_by=self.submitter_a1.id,
            filename="alpha_invoice_1.pdf",
            status=DocumentStatus.EXTRACTED,
            classification="financial",
        )
        self.doc_a2 = self._add_document(
            doc_id="doc_alpha_2",
            org_id=self.org_alpha.id,
            uploaded_by=self.submitter_a2.id,
            filename="alpha_contract_2.pdf",
            status=DocumentStatus.EXTRACTED,
            classification="legal",
        )
        self.doc_b = self._add_document(
            doc_id="doc_beta_1",
            org_id=self.org_beta.id,
            uploaded_by=self.submitter_b.id,
            filename="beta_confidential.pdf",
            status=DocumentStatus.EXTRACTED,
            classification="financial",
        )

        # 4. Extractions & Validations
        create_extractions_bulk(
            self.db,
            self.doc_a1.id,
            [ExtractionCreate(field_name="invoice_number", value="INV-ALPHA-1", confidence=0.98)],
        )
        create_extractions_bulk(
            self.db,
            self.doc_b.id,
            [ExtractionCreate(field_name="invoice_number", value="INV-BETA-CONFIDENTIAL", confidence=0.99)],
        )
        save_validation_result(
            self.db,
            document_id=self.doc_a1.id,
            organization_id=self.org_alpha.id,
            status="PASS",
        )
        save_validation_result(
            self.db,
            document_id=self.doc_b.id,
            organization_id=self.org_beta.id,
            status="PASS",
        )

        # 5. Policies
        self.policy_a = Policy(
            id="pol_alpha_1",
            organization_id=self.org_alpha.id,
            name="Alpha Finance Policy",
            domain="financial",
            content="Alpha expenses exceeding $500 require manager approval.",
            is_active=True,
        )
        self.policy_b = Policy(
            id="pol_beta_1",
            organization_id=self.org_beta.id,
            name="Beta Trade Secret Policy",
            domain="financial",
            content="Beta secret operational expenditure policy.",
            is_active=True,
        )
        self.db.add_all([self.policy_a, self.policy_b])
        self.db.commit()

    def _add_user(self, user_id: str, email: str, full_name: str, is_active: bool = True) -> User:
        user = create_user(
            self.db,
            UserCreate(
                id=user_id,
                email=email,
                full_name=full_name,
                is_active=is_active,
            ),
        )
        user.provider = "supabase"
        user.provider_subject = f"supabase-{user_id}"
        self.db.flush()
        return user

    def _add_document(
        self,
        doc_id: str,
        org_id: str,
        uploaded_by: str,
        filename: str,
        status: DocumentStatus,
        classification: str,
    ) -> Document:
        file_path = self.storage_dir / f"{doc_id}.pdf"
        file_path.write_bytes(make_valid_pdf_bytes(f"Content for {doc_id}"))

        metadata = {
            "document_id": doc_id,
            "filename": filename,
            "file_type": "application/pdf",
            "status": status.value,
            "category": classification,
            "confidence": 0.95,
            "organization_id": org_id,
            "submitter_id": uploaded_by,
            "extracted_fields": {"invoice_number": f"INV-{doc_id}"},
        }
        (self.storage_dir / "metadata" / f"{doc_id}.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )

        doc = Document(
            id=doc_id,
            organization_id=org_id,
            uploaded_by=uploaded_by,
            filename=filename,
            file_type="application/pdf",
            file_size=len(file_path.read_bytes()),
            storage_path=str(file_path.resolve()),
            status=status,
            classification=classification,
            classification_confidence=0.95,
        )
        self.db.add(doc)
        self.db.flush()
        return doc

    def headers_for(self, user: User, org_id: str | None = None) -> dict[str, str]:
        """Produce Authorization header and optional X-Organization-Id header for a user."""
        token = create_security_token(user.id, email=user.email)
        headers = {"Authorization": f"Bearer {token}"}
        if org_id is not None:
            headers["X-Organization-Id"] = org_id
        return headers


@pytest.fixture()
def security_world(db_session: Session, security_env: Path) -> SecurityWorld:
    """Fixture providing a populated SecurityWorld."""
    return SecurityWorld(db_session, security_env)
