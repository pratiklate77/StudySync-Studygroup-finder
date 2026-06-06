from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class AdminLoginRequest(BaseModel):
    """Admin login request schema."""
    email: EmailStr
    password: str


class AdminLoginResponse(BaseModel):
    """Admin login response schema."""
    access_token: str
    token_type: str = "bearer"
    admin_id: uuid.UUID
    email: str
    full_name: str
    role: str
    permissions: list[str]


class AdminProfile(BaseModel):
    """Admin profile schema."""
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    permissions: list[str]
    is_active: bool
    last_login: datetime | None
    login_count: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class CreateAdminRequest(BaseModel):
    """Create admin user request schema."""
    email: EmailStr
    password: str
    full_name: str
    role: str = "admin"
    permissions: list[str] = []


class UpdateAdminRequest(BaseModel):
    """Update admin user request schema."""
    full_name: str | None = None
    role: str | None = None
    permissions: list[str] | None = None
    is_active: bool | None = None