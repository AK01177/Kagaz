"""Authentication, credential verification, and reusable identity dependencies."""
from __future__ import annotations

import os
import time
from typing import Annotated, Collection, Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

try:
    from app.db.session import get_db
    from app.models.membership import Membership
    from app.models.organization import Organization
    from app.models.user import User
    from services.password import verify_password
except ImportError:
    from backend.app.db.session import get_db
    from backend.app.models.membership import Membership
    from backend.app.models.organization import Organization
    from backend.app.models.user import User
    from backend.services.password import verify_password

bearer = HTTPBearer(auto_error=False)

# Roles allowed to read and correct classification/extraction results
_REVIEWER_ROLES = frozenset(
    {"REVIEWER", "APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN", "COMPLIANCE", "AUDITOR"}
)
_MIN_JWT_SECRET_BYTES = 32
_DEFAULT_TOKEN_TTL_SECONDS = 3600

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _unauthenticated(message: str = "A valid bearer token is required.") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"code": "UNAUTHENTICATED", "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _require_jwt_secret(*, for_request: bool) -> str:
    secret = os.environ.get("JWT_SECRET", "")
    if len(secret.encode("utf-8")) < _MIN_JWT_SECRET_BYTES:
        if for_request:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "AUTH_NOT_CONFIGURED",
                    "message": "Authentication is not configured.",
                },
            )
        raise RuntimeError("JWT_SECRET must be configured with at least 32 bytes")
    return secret


def _get_jwt_issuer() -> str:
    return os.environ.get("JWT_ISSUER", "kagaz").strip() or "kagaz"


def _get_jwt_audience() -> str:
    return os.environ.get("JWT_AUDIENCE", "kagaz-api").strip() or "kagaz-api"


def create_access_token(
    user_id: str,
    role: str = "SUBMITTER",
    organization_id: str = "org_kagaz_primary",
    expires_in_seconds: Optional[int] = None,
) -> str:
    """Generate a signed, expiring HS256 JWT using environment-configured secrets."""
    secret = _require_jwt_secret(for_request=False)
    ttl = (
        expires_in_seconds
        if expires_in_seconds is not None
        else int(os.environ.get("JWT_EXPIRES_IN_SECONDS", _DEFAULT_TOKEN_TTL_SECONDS))
    )
    if ttl <= 0:
        raise ValueError("expires_in_seconds must be positive")
    now = int(time.time())
    payload = {
        "sub": user_id,
        "role": role,
        "organization_id": organization_id,
        "active": True,
        "iss": _get_jwt_issuer(),
        "aud": _get_jwt_audience(),
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


class LoginRequest(BaseModel):
    email: str
    password: str
    organization_id: Optional[str] = None
    # Accepted only so caller-supplied privilege fields are ignored instead of 422,
    # never trusted when determining authorization.
    role: Optional[str] = None


def get_auth_db(
    db: Annotated[Optional[Session], Depends(get_db)] = None,
):
    """Yield the configured database session for identity resolution."""
    yield db


def _active_memberships_query(db: Session, *, user_id: str):
    return (
        db.query(Membership)
        .join(Organization, Organization.id == Membership.organization_id)
        .filter(
            Membership.user_id == user_id,
            Membership.is_active.is_(True),
            Organization.is_active.is_(True),
        )
    )


def _resolve_active_membership(
    db: Session,
    *,
    user_id: str,
    organization_id: Optional[str] = None,
) -> Optional[Membership]:
    query = _active_memberships_query(db, user_id=user_id)
    if organization_id is not None:
        query = query.filter(Membership.organization_id == organization_id)
    else:
        query = query.order_by(Membership.created_at.asc(), Membership.id.asc())
    return query.first()


def _list_active_memberships(db: Session, *, user_id: str) -> list[dict[str, str]]:
    rows = (
        _active_memberships_query(db, user_id=user_id)
        .order_by(Membership.created_at.asc(), Membership.id.asc())
        .all()
    )
    return [
        {
            "organization_id": row.organization_id,
            "role": row.role.value if hasattr(row.role, "value") else str(row.role),
        }
        for row in rows
    ]


def _decode_bearer_token(raw_token: str) -> dict:
    secret = _require_jwt_secret(for_request=True)
    try:
        claims = jwt.decode(
            raw_token,
            secret,
            algorithms=["HS256"],
            issuer=_get_jwt_issuer(),
            audience=_get_jwt_audience(),
            options={
                "require": [
                    "sub",
                    "exp",
                    "iat",
                    "iss",
                    "aud",
                    "role",
                    "organization_id",
                    "active",
                ]
            },
        )
        for key in ("sub", "organization_id", "role"):
            if not isinstance(claims[key], str) or not claims[key].strip():
                raise jwt.InvalidTokenError("Invalid identity claim")
        if not isinstance(claims["active"], bool):
            raise jwt.InvalidTokenError("Invalid active claim")
    except jwt.InvalidTokenError as exc:
        raise _unauthenticated() from exc
    return claims


@router.post("/login")
async def login(
    payload: LoginRequest,
    db: Annotated[Optional[Session], Depends(get_auth_db)] = None,
):
    """Verify persistent user credentials and issue a signed expiring JWT."""
    email_clean = payload.email.strip().lower()
    if not email_clean or not payload.password:
        raise _unauthenticated("Valid email and password credentials are required.")

    if db is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "AUTH_DATABASE_UNAVAILABLE",
                "message": "Authentication requires an active database connection.",
            },
        )

    db_user = db.query(User).filter(User.email == email_clean).first()
    stored_hash = db_user.password_hash if db_user is not None else None
    if db_user is None or not verify_password(payload.password, stored_hash):
        raise _unauthenticated("Invalid email or password.")

    if not db_user.is_active:
        raise HTTPException(
            status_code=403,
            detail={"code": "ACCOUNT_INACTIVE", "message": "An active user account is required."},
        )

    target_org = payload.organization_id.strip() if payload.organization_id else None
    membership = _resolve_active_membership(
        db,
        user_id=db_user.id,
        organization_id=target_org,
    )
    if membership is None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "MEMBERSHIP_REQUIRED",
                "message": "An active organization membership is required.",
            },
        )

    _require_jwt_secret(for_request=True)
    assigned_role = (
        membership.role.value if hasattr(membership.role, "value") else str(membership.role)
    )
    organization_id = membership.organization_id
    user_name = db_user.full_name or email_clean.split("@")[0].replace(".", " ").title()

    token = create_access_token(
        user_id=db_user.id,
        role=assigned_role,
        organization_id=organization_id,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": db_user.id,
            "name": user_name,
            "email": db_user.email,
            "role": assigned_role,
            "organization_id": organization_id,
        },
    }


def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)],
    db: Annotated[Optional[Session], Depends(get_auth_db)] = None,
    x_organization_id: Annotated[Optional[str], Header(alias="X-Organization-Id")] = None,
) -> dict:
    """Verify bearer JWT and resolve server-side identity, active organization, and role."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthenticated()

    raw_token = credentials.credentials.strip()
    if not raw_token or raw_token in ("undefined", "null"):
        raise _unauthenticated()

    claims = _decode_bearer_token(raw_token)
    if claims["active"] is not True:
        raise HTTPException(
            status_code=403,
            detail={"code": "ACCOUNT_INACTIVE", "message": "An active account is required."},
        )

    requested_org: Optional[str] = None
    if x_organization_id is not None:
        requested_org = x_organization_id.strip()
        if not requested_org:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "MEMBERSHIP_REQUIRED",
                    "message": "An active organization membership is required.",
                },
            )

    target_organization_id = requested_org or claims["organization_id"]

    if db is not None:
        db_user = db.query(User).filter(User.id == claims["sub"]).first()
        if db_user is None:
            raise _unauthenticated("Authenticated identity is not registered.")
        if not db_user.is_active:
            raise HTTPException(
                status_code=403,
                detail={"code": "ACCOUNT_INACTIVE", "message": "An active account is required."},
            )
        membership = _resolve_active_membership(
            db,
            user_id=db_user.id,
            organization_id=target_organization_id,
        )
        if membership is None:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "MEMBERSHIP_REQUIRED",
                    "message": "An active organization membership is required.",
                },
            )
        resolved_role = (
            membership.role.value if hasattr(membership.role, "value") else str(membership.role)
        )
        return {
            **claims,
            "sub": db_user.id,
            "email": db_user.email,
            "name": db_user.full_name,
            "organization_id": membership.organization_id,
            "role": resolved_role,
            "active": True,
            "memberships": _list_active_memberships(db, user_id=db_user.id),
        }

    if requested_org is not None and requested_org != claims["organization_id"]:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "MEMBERSHIP_REQUIRED",
                "message": "An active organization membership is required.",
            },
        )

    return {
        **claims,
        "memberships": claims.get("memberships")
        or [{"organization_id": claims["organization_id"], "role": claims["role"]}],
    }


require_authenticated_user = get_current_user


def get_active_organization_id(
    identity: Annotated[dict, Depends(get_current_user)],
) -> str:
    """Return the verified active organization context for the authenticated user."""
    organization_id = identity.get("organization_id")
    if not isinstance(organization_id, str) or not organization_id.strip():
        raise HTTPException(
            status_code=403,
            detail={
                "code": "MEMBERSHIP_REQUIRED",
                "message": "An active organization membership is required.",
            },
        )
    return organization_id.strip()


def require_organization_membership(
    identity: dict,
    target_organization_id: Optional[str],
    *,
    forbidden_message: str = "Forbidden: Resource belongs to a different organization",
) -> str:
    """Fail closed unless the caller's active organization matches target_organization_id."""
    user_org = identity.get("organization_id")
    if not isinstance(user_org, str) or not user_org.strip():
        raise HTTPException(
            status_code=403,
            detail={
                "code": "MEMBERSHIP_REQUIRED",
                "message": "An active organization membership is required.",
            },
        )
    if not isinstance(target_organization_id, str) or not target_organization_id.strip():
        raise HTTPException(status_code=403, detail=forbidden_message)
    if target_organization_id.strip() != user_org.strip():
        raise HTTPException(status_code=403, detail=forbidden_message)
    return user_org.strip()


@router.get("/me")
def get_authenticated_profile(
    identity: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Return the server-resolved identity for the currently authenticated caller."""
    return {
        "user_id": identity["sub"],
        "email": identity.get("email"),
        "name": identity.get("name"),
        "role": identity["role"],
        "organization_id": identity["organization_id"],
        "active": identity["active"],
    }


@router.get("/memberships")
def list_authenticated_memberships(
    identity: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """List verified active organization memberships for the authenticated caller."""
    memberships = identity.get("memberships") or [
        {"organization_id": identity["organization_id"], "role": identity["role"]}
    ]
    return {
        "user_id": identity["sub"],
        "active_organization_id": identity["organization_id"],
        "memberships": memberships,
    }


def _require_role_access(
    identity: dict,
    allowed_roles: Collection[str],
    *,
    forbidden_code: str,
    message: str,
) -> dict:
    if identity.get("role") not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail={"code": forbidden_code, "message": message},
        )
    return identity


def require_submitter(
    identity: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Require an active authenticated submitter."""
    return _require_role_access(
        identity,
        ("SUBMITTER",),
        forbidden_code="UPLOAD_FORBIDDEN",
        message="An active submitter account is required.",
    )


def require_reviewer(
    identity: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Allow REVIEWER and higher roles to access correction and extraction endpoints."""
    return _require_role_access(
        identity,
        _REVIEWER_ROLES,
        forbidden_code="REVIEW_FORBIDDEN",
        message="An active reviewer account is required.",
    )


def require_policy_reader(
    identity: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Require an active authenticated user for tenant-scoped policy access."""
    return identity


def require_workflow_actor(
    identity: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Require an active authenticated user for workflow endpoints."""
    return identity


def require_policy_admin(
    identity: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Allow organization admins to manage policy knowledge for their tenant."""
    return _require_role_access(
        identity,
        ("ORG_ADMIN",),
        forbidden_code="POLICY_ADMIN_REQUIRED",
        message="An active organization admin account is required.",
    )
