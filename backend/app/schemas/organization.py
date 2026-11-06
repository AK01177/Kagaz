"""
Pydantic schemas for Organization entity.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class OrganizationBase(BaseModel):
    name: str = Field(..., description="Organization display name")
    slug: str = Field(..., description="Unique URL-friendly slug/identifier for the organization")


class OrganizationCreate(OrganizationBase):
    id: Optional[str] = None
    is_active: bool = True


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    is_active: Optional[bool] = None


class OrganizationResponse(OrganizationBase):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

