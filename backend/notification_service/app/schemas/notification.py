from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    title: str
    message: str
    context: dict
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    total: int
    page: int
    per_page: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    count: int


class NewCountResponse(BaseModel):
    count: int


class NotificationPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    email_enabled: bool
    push_enabled: bool
    in_app_enabled: bool
    notification_types: dict[str, bool]


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: bool | None = None
    push_enabled: bool | None = None
    in_app_enabled: bool | None = None
    notification_types: dict[str, bool] | None = None


class TemplateCreate(BaseModel):
    event_type: str
    title_template: str
    message_template: str
    is_active: bool = True


class TemplateRead(TemplateCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID