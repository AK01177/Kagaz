"""
Pydantic schemas for in-app workflow notifications (BE-13).
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    """Public representation of an in-app notification."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    recipient_user_id: str
    organization_id: str
    document_id: Optional[str] = None
    notification_type: str
    title: str
    body: Optional[str] = None
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated list of notifications for the current authenticated user."""
    items: List[NotificationResponse]
    total: int = Field(..., ge=0)
    unread_count: int = Field(..., ge=0)


class MarkReadResponse(BaseModel):
    """Response returned when marking notifications read."""
    success: bool = True
    notification_id: Optional[str] = None
    updated_count: int = 1
