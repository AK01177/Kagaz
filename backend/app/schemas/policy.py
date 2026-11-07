"""
Pydantic schemas for BE-08 Policy Management.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PolicyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Policy title")
    domain: str = Field(..., min_length=1, max_length=50, description="Domain (financial, hr, academic, compliance)")
    content: str = Field(..., min_length=1, description="Policy text or rule definitions")
    description: Optional[str] = Field(None, max_length=500, description="Brief policy description")


class PolicyCreate(PolicyBase):
    pass


class PolicyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    domain: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    content: Optional[str] = Field(None, min_length=1)
    changelog: Optional[str] = Field(None, description="Notes on what changed in this version")
    is_active: Optional[bool] = None


class PolicyVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    policy_id: str
    version: str
    content: str
    changelog: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime


class PolicyResponse(PolicyBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    current_version: str
    is_active: bool
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
