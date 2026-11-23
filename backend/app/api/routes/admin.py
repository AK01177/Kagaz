"""Organization-scoped administration API routes protected by RBAC permissions."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.auth import Permission, require_permission
from app.crud.organization import unique_slug
from app.db.session import get_db
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User
from app.schemas.admin import (
    AdminMemberCreateRequest,
    AdminMemberResponse,
    AdminMemberUpdateRequest,
    AdminOrganizationCreateRequest,
    AdminOrganizationListResponse,
    AdminOrganizationResponse,
    AdminUserListResponse,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_db(db: Optional[Session]) -> Session:
    if db is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "DATABASE_UNAVAILABLE",
                "message": "Database connection is required for organization administration.",
            },
        )
    return db


def _enforce_target_org(identity: dict, requested_org_id: Optional[str]) -> str:
    active_org = str(identity.get("organization_id") or "").strip()
    if not active_org:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "MEMBERSHIP_REQUIRED",
                "message": "An active organization membership is required.",
            },
        )
    if requested_org_id is not None and requested_org_id.strip() != active_org:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ADMIN_TENANT_FORBIDDEN",
                "message": "Administrators cannot administer another organization.",
            },
        )
    return active_org


@router.get("/organization", response_model=AdminOrganizationResponse)
def get_admin_organization_summary(
    identity: Annotated[dict, Depends(require_permission(Permission.ADMIN_ORG_READ))],
    organization_id: Optional[str] = Query(default=None),
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> AdminOrganizationResponse:
    """Return active organization metadata and member count for an organization admin."""
    session = _require_db(db)
    active_org_id = _enforce_target_org(identity, organization_id)

    org = session.query(Organization).filter(Organization.id == active_org_id).first()
    if org is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "ORGANIZATION_NOT_FOUND", "message": "Organization not found."},
        )

    active_count = (
        session.query(Membership)
        .filter(
            Membership.organization_id == active_org_id,
            Membership.is_active.is_(True),
        )
        .count()
    )
    return AdminOrganizationResponse(
        organization_id=org.id,
        name=org.name,
        slug=org.slug,
        is_active=bool(org.is_active),
        active_member_count=active_count,
    )


@router.get("/users", response_model=AdminUserListResponse)
def list_organization_users(
    identity: Annotated[dict, Depends(require_permission(Permission.ADMIN_USERS_READ))],
    organization_id: Optional[str] = Query(default=None),
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> AdminUserListResponse:
    """List users and their roles strictly within the administrator's active organization."""
    session = _require_db(db)
    active_org_id = _enforce_target_org(identity, organization_id)

    rows = (
        session.query(Membership, User)
        .join(User, User.id == Membership.user_id)
        .filter(Membership.organization_id == active_org_id)
        .order_by(User.email.asc())
        .all()
    )
    return AdminUserListResponse(
        organization_id=active_org_id,
        users=[
            AdminMemberResponse(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                user_active=bool(user.is_active),
                organization_id=membership.organization_id,
                role=(
                    membership.role.value
                    if hasattr(membership.role, "value")
                    else str(membership.role)
                ),
                membership_active=bool(membership.is_active),
            )
            for membership, user in rows
        ],
    )


@router.put("/users/{user_id}", response_model=AdminMemberResponse)
def update_organization_member(
    user_id: str,
    payload: AdminMemberUpdateRequest,
    identity: Annotated[dict, Depends(require_permission(Permission.ADMIN_USERS_MANAGE))],
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> AdminMemberResponse:
    """Update a member's role or status strictly within the administrator's organization."""
    session = _require_db(db)
    active_org_id = _enforce_target_org(identity, payload.organization_id)

    if payload.role is None and payload.is_active is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_ADMIN_UPDATE",
                "message": "Provide a role or is_active update.",
            },
        )

    caller_role = str(identity.get("role") or "").strip().upper()
    if payload.role == MembershipRole.SYSTEM_ADMIN and caller_role != "SYSTEM_ADMIN":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "SYSTEM_ADMIN_REQUIRED",
                "message": "Only a system administrator may grant the SYSTEM_ADMIN role.",
            },
        )

    row = (
        session.query(Membership, User)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.user_id == user_id,
            Membership.organization_id == active_org_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MEMBER_NOT_FOUND",
                "message": "User membership not found in the active organization.",
            },
        )

    membership, user = row
    if payload.role is not None:
        membership.role = payload.role
    if payload.is_active is not None:
        membership.is_active = payload.is_active

    session.commit()
    session.refresh(membership)
    return AdminMemberResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        user_active=bool(user.is_active),
        organization_id=membership.organization_id,
        role=(
            membership.role.value
            if hasattr(membership.role, "value")
            else str(membership.role)
        ),
        membership_active=bool(membership.is_active),
    )


def _member_response(membership: Membership, user: User) -> AdminMemberResponse:
    return AdminMemberResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        user_active=bool(user.is_active),
        organization_id=membership.organization_id,
        role=membership.role.value if hasattr(membership.role, "value") else str(membership.role),
        membership_active=bool(membership.is_active),
    )


def _get_or_create_user(session: Session, email: str, full_name: Optional[str]) -> User:
    """Find the profile for this email, or create one that links to Supabase on first sign-in."""
    email = email.strip().lower()
    user = session.query(User).filter(func.lower(User.email) == email).first()
    if user is None:
        user = User(email=email, full_name=full_name, is_active=True)
        session.add(user)
        session.flush()
    return user


def _org_response(session: Session, org: Organization) -> AdminOrganizationResponse:
    count = session.query(Membership).filter(
        Membership.organization_id == org.id, Membership.is_active.is_(True)
    ).count()
    return AdminOrganizationResponse(
        organization_id=org.id, name=org.name, slug=org.slug,
        is_active=bool(org.is_active), active_member_count=count,
    )


@router.post("/users", response_model=AdminMemberResponse, status_code=201)
def add_organization_member(
    payload: AdminMemberCreateRequest,
    identity: Annotated[dict, Depends(require_permission(Permission.ADMIN_USERS_MANAGE))],
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> AdminMemberResponse:
    """Add a person to the administrator's organization. They sign up with this email to get in."""
    session = _require_db(db)
    org_id = _enforce_target_org(identity, None)

    if payload.role == MembershipRole.SYSTEM_ADMIN and str(identity.get("role")).upper() != "SYSTEM_ADMIN":
        raise HTTPException(status_code=403, detail={
            "code": "SYSTEM_ADMIN_REQUIRED",
            "message": "Only a system administrator may grant the SYSTEM_ADMIN role.",
        })

    user = _get_or_create_user(session, payload.email, payload.full_name)
    existing = session.query(Membership).filter(
        Membership.user_id == user.id, Membership.organization_id == org_id
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail={
            "code": "MEMBER_ALREADY_EXISTS",
            "message": "This person is already a member of the organization. Update their role instead.",
        })
    membership = Membership(user_id=user.id, organization_id=org_id, role=payload.role, is_active=True)
    session.add(membership)
    session.commit()
    session.refresh(membership)
    return _member_response(membership, user)


@router.get("/organizations", response_model=AdminOrganizationListResponse)
def list_organizations(
    identity: Annotated[dict, Depends(require_permission(Permission.ADMIN_ORGS_MANAGE))],
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> AdminOrganizationListResponse:
    """List every organization on the platform (system administrators only)."""
    session = _require_db(db)
    orgs = session.query(Organization).order_by(Organization.name.asc()).all()
    return AdminOrganizationListResponse(organizations=[_org_response(session, o) for o in orgs])


@router.post("/organizations", response_model=AdminOrganizationResponse, status_code=201)
def create_organization(
    payload: AdminOrganizationCreateRequest,
    identity: Annotated[dict, Depends(require_permission(Permission.ADMIN_ORGS_MANAGE))],
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> AdminOrganizationResponse:
    """Create an organization and make the given email its first ORG_ADMIN."""
    session = _require_db(db)
    org = Organization(name=payload.name.strip(), slug=unique_slug(session, payload.name), is_active=True)
    session.add(org)
    session.flush()
    admin_user = _get_or_create_user(session, payload.admin_email, payload.admin_name)
    session.add(Membership(
        user_id=admin_user.id, organization_id=org.id, role=MembershipRole.ORG_ADMIN, is_active=True,
    ))
    session.commit()
    session.refresh(org)
    return _org_response(session, org)
