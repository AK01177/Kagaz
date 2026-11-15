"""Authentication, credential verification, and reusable identity dependencies."""
from __future__ import annotations

import os
from typing import Annotated, Callable, Collection, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func
from sqlalchemy.orm import Session

try:
    from app.core.permissions import (
        PERMISSION_ERROR_DETAILS,
        ROLE_PERMISSIONS,
        Permission,
        get_permissions_for_role,
        identity_has_permission,
        roles_with_permission,
    )
    from app.db.session import get_db
    from app.models.membership import Membership
    from app.models.organization import Organization
    from app.models.user import User
except ImportError:
    from backend.app.core.permissions import (
        PERMISSION_ERROR_DETAILS,
        ROLE_PERMISSIONS,
        Permission,
        get_permissions_for_role,
        identity_has_permission,
        roles_with_permission,
    )
    from backend.app.db.session import get_db
    from backend.app.models.membership import Membership
    from backend.app.models.organization import Organization
    from backend.app.models.user import User

bearer = HTTPBearer(auto_error=False)

# Roles allowed to perform document classification/extraction review mutations
_REVIEWER_ROLES = roles_with_permission(Permission.DOCUMENTS_CORRECT_CLASSIFICATION)
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _unauthenticated(message: str = "A valid bearer token is required.") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"code": "UNAUTHENTICATED", "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _supabase_user_from_token(raw_token: str) -> dict:
    """Ask Supabase Auth to validate the access token and return its user record."""
    project_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    anon_key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not project_url or not anon_key:
        raise HTTPException(status_code=503, detail={
            "code": "AUTH_NOT_CONFIGURED", "message": "Supabase authentication is not configured."
        })
    try:
        response = httpx.get(
            f"{project_url}/auth/v1/user", timeout=5.0,
            headers={"apikey": anon_key, "Authorization": f"Bearer {raw_token}"},
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail={
            "code": "AUTH_PROVIDER_UNAVAILABLE", "message": "Supabase Auth is temporarily unavailable."
        }) from exc
    if response.status_code != 200:
        raise _unauthenticated()
    user = response.json()
    if not isinstance(user, dict) or not user.get("id") or not user.get("email"):
        raise _unauthenticated()
    return user


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


def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)],
    db: Annotated[Optional[Session], Depends(get_auth_db)] = None,
    x_organization_id: Annotated[Optional[str], Header(alias="X-Organization-Id")] = None,
) -> dict:
    """Verify Supabase access token and resolve Kagaz membership and role."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthenticated()

    raw_token = credentials.credentials.strip()
    if not raw_token or raw_token in ("undefined", "null"):
        raise _unauthenticated()

    auth_user = _supabase_user_from_token(raw_token)
    supabase_user_id = str(auth_user["id"])
    email = str(auth_user["email"]).strip().lower()
    if not auth_user.get("email_confirmed_at"):
        raise HTTPException(status_code=403, detail={
            "code": "EMAIL_NOT_CONFIRMED", "message": "Confirm your email address with Supabase before signing in."
        })

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

    if db is not None:
        db_user = db.query(User).filter(User.provider == "supabase", User.provider_subject == supabase_user_id).first()
        if db_user is None:
            # Link an existing Kagaz profile by the email returned by Supabase Auth.
            db_user = db.query(User).filter(func.lower(User.email) == email).first()
            if db_user is not None and db_user.provider == "supabase" and db_user.provider_subject != supabase_user_id:
                raise HTTPException(status_code=409, detail={
                    "code": "IDENTITY_ALREADY_LINKED", "message": "This Kagaz profile is linked to another identity provider account."
                })
            if db_user is not None:
                db_user.provider = "supabase"
                db_user.provider_subject = supabase_user_id
                db.commit()
        if db_user is None:
            raise HTTPException(status_code=403, detail={
                "code": "MEMBERSHIP_REQUIRED", "message": "Your Supabase account is valid, but an organization administrator must add you to a Kagaz workspace."
            })
        if not db_user.is_active:
            raise HTTPException(
                status_code=403,
                detail={"code": "ACCOUNT_INACTIVE", "message": "An active account is required."},
            )
        membership = _resolve_active_membership(
            db,
            user_id=db_user.id,
            organization_id=requested_org,
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
            "sub": db_user.id,
            "supabase_user_id": supabase_user_id,
            "email": email,
            "name": db_user.full_name or (auth_user.get("user_metadata") or {}).get("full_name") or email.split("@")[0],
            "organization_id": membership.organization_id,
            "role": resolved_role,
            "permissions": sorted(p.value for p in get_permissions_for_role(resolved_role)),
            "active": True,
            "memberships": _list_active_memberships(db, user_id=db_user.id),
        }

    raise HTTPException(status_code=503, detail={
        "code": "AUTH_DATABASE_UNAVAILABLE", "message": "Kagaz organization membership storage is unavailable."
    })


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
    forbidden_code: str = "TENANT_ACCESS_DENIED",
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
        raise HTTPException(
            status_code=403,
            detail={"code": forbidden_code, "message": forbidden_message},
        )
    if target_organization_id.strip() != user_org.strip():
        raise HTTPException(
            status_code=403,
            detail={"code": forbidden_code, "message": forbidden_message},
        )
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


def _require_permission_access(
    identity: dict,
    permission: Permission | str,
    *,
    forbidden_code: Optional[str] = None,
    message: Optional[str] = None,
) -> dict:
    perm = permission if isinstance(permission, Permission) else Permission(permission)
    if not identity_has_permission(identity, perm):
        default_code, default_message = PERMISSION_ERROR_DETAILS.get(
            perm,
            ("FORBIDDEN", "You do not have permission to perform this action."),
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": forbidden_code or default_code,
                "message": message or default_message,
            },
        )
    return identity


def require_permission(
    permission: Permission | str,
    *,
    forbidden_code: Optional[str] = None,
    message: Optional[str] = None,
) -> Callable[..., dict]:
    """Build a reusable FastAPI dependency enforcing a single matrix permission."""
    perm = permission if isinstance(permission, Permission) else Permission(permission)

    def _dependency(
        identity: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        return _require_permission_access(
            identity,
            perm,
            forbidden_code=forbidden_code,
            message=message,
        )

    return _dependency


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
    """Require permission to upload/submit documents."""
    return _require_permission_access(
        identity,
        Permission.DOCUMENTS_UPLOAD,
        forbidden_code="UPLOAD_FORBIDDEN",
        message="An active submitter or admin account is required.",
    )


def require_reviewer(
    identity: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Require permission to perform reviewer classification/extraction updates."""
    return _require_permission_access(
        identity,
        Permission.DOCUMENTS_CORRECT_CLASSIFICATION,
        forbidden_code="REVIEW_FORBIDDEN",
        message="An active reviewer account is required.",
    )


def require_extraction_reader(
    identity: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Require permission to read structured document extraction records."""
    return _require_permission_access(
        identity,
        Permission.DOCUMENTS_READ_EXTRACTION,
        forbidden_code="EXTRACTION_READ_FORBIDDEN",
        message="You do not have permission to inspect extracted document fields.",
    )


def require_approver(
    identity: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Require permission to issue final document approval or rejection decisions."""
    return _require_permission_access(
        identity,
        Permission.WORKFLOW_DECIDE,
        forbidden_code="APPROVAL_FORBIDDEN",
        message="An authorized approver role is required to decide documents.",
    )


def require_org_admin(
    identity: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Require organization administrator permission for tenant user/org management."""
    return _require_permission_access(
        identity,
        Permission.ADMIN_USERS_MANAGE,
        forbidden_code="ADMIN_FORBIDDEN",
        message="An active organization administrator account is required.",
    )


def require_policy_reader(
    identity: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Require permission to inspect organization policy knowledge."""
    return _require_permission_access(
        identity,
        Permission.POLICIES_READ,
        forbidden_code="POLICY_READ_FORBIDDEN",
        message="You do not have permission to read organization policies.",
    )


def require_workflow_actor(
    identity: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Require an active authenticated user for workflow endpoints."""
    return identity


def require_policy_admin(
    identity: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Allow organization admins to manage policy knowledge for their tenant."""
    return _require_permission_access(
        identity,
        Permission.POLICIES_ADMIN,
        forbidden_code="POLICY_ADMIN_REQUIRED",
        message="An active organization admin account is required.",
    )


require_document_reader = require_permission(Permission.DOCUMENTS_READ)
require_classifier = require_permission(Permission.DOCUMENTS_CLASSIFY)
require_extraction_runner = require_permission(Permission.DOCUMENTS_RUN_EXTRACTION)
require_validator = require_permission(Permission.DOCUMENTS_VALIDATE)
require_audit_reader = require_permission(Permission.AUDIT_READ)
