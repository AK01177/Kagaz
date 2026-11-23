"""Pydantic schemas for organization-scoped administration endpoints."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.membership import MembershipRole


class AdminOrganizationResponse(BaseModel):
    organization_id: str
    name: str
    slug: str
    is_active: bool
    active_member_count: int


class AdminMemberResponse(BaseModel):
    user_id: str
    email: str
    full_name: Optional[str] = None
    user_active: bool
    organization_id: str
    role: str
    membership_active: bool


class AdminUserListResponse(BaseModel):
    organization_id: str
    users: List[AdminMemberResponse]


class AdminMemberUpdateRequest(BaseModel):
    role: Optional[MembershipRole] = None
    is_active: Optional[bool] = None
    organization_id: Optional[str] = None


_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class AdminMemberCreateRequest(BaseModel):
    """Add (invite) a person to the admin's organization by email."""

    email: str = Field(pattern=_EMAIL_PATTERN, max_length=254)
    role: MembershipRole
    full_name: Optional[str] = Field(default=None, max_length=200)


class AdminOrganizationCreateRequest(BaseModel):
    """Create an organization together with its first ORG_ADMIN."""

    name: str = Field(min_length=2, max_length=120)
    admin_email: str = Field(pattern=_EMAIL_PATTERN, max_length=254)
    admin_name: Optional[str] = Field(default=None, max_length=200)


class AdminOrganizationListResponse(BaseModel):
    organizations: List[AdminOrganizationResponse]
