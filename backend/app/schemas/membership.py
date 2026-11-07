"""
Pydantic schemas for Membership entity.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.membership import MembershipRole


class MembershipBase(BaseModel):
    organization_id: str = Field(..., description="Target organization ID")
    user_id: str = Field(..., description="Target user ID")
    role: MembershipRole = Field(default=MembershipRole.SUBMITTER, description="Assigned authorization role")


class MembershipCreate(MembershipBase):
    id: Optional[str] = None
    is_active: bool = True


class MembershipUpdate(BaseModel):
    role: Optional[MembershipRole] = None
    is_active: Optional[bool] = None


class MembershipResponse(MembershipBase):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

