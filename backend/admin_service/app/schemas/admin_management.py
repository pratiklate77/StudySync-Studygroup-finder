from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator

from app.models.admin_user import AdminUser


class AdminCreateRequest(BaseModel):
    """Request schema for creating new admin."""
    
    email: EmailStr = Field(..., description="Admin email address")
    password: str = Field(..., min_length=8, description="Admin password (min 8 chars)")
    full_name: str = Field(..., min_length=2, max_length=255, description="Full name")
    role: str = Field(..., description="Admin role (admin, moderator, super_admin)")
    permissions: Optional[List[str]] = Field(default=None, description="Custom permissions")
    
    @validator("role")
    def validate_role(cls, v):
        allowed_roles = ["admin", "moderator", "super_admin"]
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of: {allowed_roles}")
        return v
    
    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        
        # Check for at least one digit and one letter
        has_digit = any(c.isdigit() for c in v)
        has_letter = any(c.isalpha() for c in v)
        
        if not (has_digit and has_letter):
            raise ValueError("Password must contain at least one letter and one digit")
        
        return v


class AdminUpdateRequest(BaseModel):
    """Request schema for updating admin."""
    
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    role: Optional[str] = Field(None, description="Admin role")
    permissions: Optional[List[str]] = Field(None, description="Custom permissions")
    is_active: Optional[bool] = Field(None, description="Active status")
    
    @validator("role")
    def validate_role(cls, v):
        if v is not None:
            allowed_roles = ["admin", "moderator", "super_admin"]
            if v not in allowed_roles:
                raise ValueError(f"Role must be one of: {allowed_roles}")
        return v


class AdminResponse(BaseModel):
    """Response schema for admin data."""
    
    id: UUID
    email: str
    full_name: str
    role: str
    permissions: List[str]
    is_active: bool
    last_login: Optional[datetime]
    login_count: int
    created_at: datetime
    
    @classmethod
    def from_model(cls, admin: AdminUser) -> AdminResponse:
        """Create response from admin model."""
        return cls(
            id=admin.id,
            email=admin.email,
            full_name=admin.full_name,
            role=admin.role,
            permissions=admin.permissions or [],
            is_active=admin.is_active,
            last_login=admin.last_login,
            login_count=admin.login_count,
            created_at=admin.created_at,
        )


class AdminListResponse(BaseModel):
    """Response schema for admin list."""
    
    admins: List[AdminResponse]
    total: int
    skip: int
    limit: int


class PasswordChangeRequest(BaseModel):
    """Request schema for password change."""
    
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    
    @validator("new_password")
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        
        # Check for at least one digit and one letter
        has_digit = any(c.isdigit() for c in v)
        has_letter = any(c.isalpha() for c in v)
        
        if not (has_digit and has_letter):
            raise ValueError("Password must contain at least one letter and one digit")
        
        return v


class AdminPermissions:
    """Available admin permissions."""
    
    # User management
    VIEW_USERS = "view_users"
    SUSPEND_USERS = "suspend_users"
    ACTIVATE_USERS = "activate_users"
    DELETE_USERS = "delete_users"
    
    # Admin management
    VIEW_ADMINS = "view_admins"
    CREATE_ADMIN = "create_admin"
    UPDATE_ADMIN = "update_admin"
    DEACTIVATE_ADMIN = "deactivate_admin"
    ACTIVATE_ADMIN = "activate_admin"
    RESET_PASSWORD = "reset_password"
    
    # Analytics
    VIEW_ANALYTICS = "view_analytics"
    EXPORT_DATA = "export_data"
    
    # System
    VIEW_SYSTEM_HEALTH = "view_system_health"
    MANAGE_SETTINGS = "manage_settings"
    
    # Content moderation
    MODERATE_CONTENT = "moderate_content"
    DELETE_CONTENT = "delete_content"
    
    @classmethod
    def get_role_permissions(cls, role: str) -> List[str]:
        """Get default permissions for role."""
        if role == "super_admin":
            return [
                cls.VIEW_USERS, cls.SUSPEND_USERS, cls.ACTIVATE_USERS, cls.DELETE_USERS,
                cls.VIEW_ADMINS, cls.CREATE_ADMIN, cls.UPDATE_ADMIN, 
                cls.DEACTIVATE_ADMIN, cls.ACTIVATE_ADMIN, cls.RESET_PASSWORD,
                cls.VIEW_ANALYTICS, cls.EXPORT_DATA,
                cls.VIEW_SYSTEM_HEALTH, cls.MANAGE_SETTINGS,
                cls.MODERATE_CONTENT, cls.DELETE_CONTENT,
            ]
        elif role == "admin":
            return [
                cls.VIEW_USERS, cls.SUSPEND_USERS, cls.ACTIVATE_USERS,
                cls.VIEW_ADMINS,
                cls.VIEW_ANALYTICS,
                cls.VIEW_SYSTEM_HEALTH,
                cls.MODERATE_CONTENT,
            ]
        elif role == "moderator":
            return [
                cls.VIEW_USERS,
                cls.MODERATE_CONTENT,
            ]
        else:
            return []