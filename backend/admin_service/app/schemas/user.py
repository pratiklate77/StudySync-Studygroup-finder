from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr


class UserSummary(BaseModel):
    """User summary for admin dashboard."""
    id: uuid.UUID
    email: str
    full_name: str | None
    role: str  # student, tutor
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: datetime | None
    
    class Config:
        from_attributes = True


class TutorSummary(UserSummary):
    """Tutor summary with additional fields."""
    subjects: list[str]
    hourly_rate: float | None
    rating: float | None
    total_ratings: int
    total_sessions: int
    verification_status: str


class UserDetails(BaseModel):
    """Detailed user information for admin."""
    id: uuid.UUID
    email: str
    full_name: str | None
    phone: str | None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None
    
    # Additional details based on role
    profile_data: dict[str, Any] | None = None
    
    class Config:
        from_attributes = True


class UserActionRequest(BaseModel):
    """Request to perform action on user."""
    reason: str | None = None


class UserListResponse(BaseModel):
    """Response for user list with pagination."""
    users: list[UserSummary]
    total: int
    page: int
    per_page: int
    total_pages: int


class UserSearchFilters(BaseModel):
    """Filters for user search."""
    role: str | None = None  # student, tutor
    is_active: bool | None = None
    is_verified: bool | None = None
    search: str | None = None  # Search in name/email
    created_after: datetime | None = None
    created_before: datetime | None = None