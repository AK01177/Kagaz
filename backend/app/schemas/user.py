"""
Pydantic schemas for User and UserProviderMapping entities.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: str = Field(..., description="Unique email address of the user")
    full_name: Optional[str] = Field(None, description="Display name of the user")


class UserCreate(UserBase):
    id: Optional[str] = None
    is_active: bool = True
    password: Optional[str] = Field(None, min_length=1, description="Plaintext password hashed before storage")
    provider: Optional[str] = Field(None, description="External identity provider name (e.g. google, azure_ad)")
    provider_subject: Optional[str] = Field(None, description="Subject ID within the identity provider")


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=1, description="New plaintext password hashed before storage")
    provider: Optional[str] = None
    provider_subject: Optional[str] = None


class UserResponse(UserBase):
    id: str
    is_active: bool
    provider: Optional[str] = None
    provider_subject: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProviderMappingBase(BaseModel):
    provider: str
    provider_subject: str


class UserProviderMappingCreate(UserProviderMappingBase):
    id: Optional[str] = None
    user_id: str


class UserProviderMappingResponse(UserProviderMappingBase):
    id: str
    user_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

