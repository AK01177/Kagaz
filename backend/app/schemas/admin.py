"""Pydantic schemas for organization-scoped administration endpoints."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

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
