from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.admin_action import AdminAction


class AdminUser(Base):
    """Admin user model for authentication and authorization."""
    
    email: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        nullable=False, 
        index=True
    )
    
    password_hash: Mapped[str] = mapped_column(
        String(255), 
        nullable=False
    )
    
    full_name: Mapped[str] = mapped_column(
        String(255), 
        nullable=False
    )
    
    role: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        default="admin"
    )  # super_admin, admin, moderator
    
    permissions: Mapped[list[str]] = mapped_column(
        JSONB, 
        nullable=False, 
        default=list
    )  # List of permission strings
    
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        nullable=False
    )
    
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )
    
    login_count: Mapped[int] = mapped_column(
        default=0, 
        nullable=False
    )
    
    notes: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    
    # Relationships
    actions: Mapped[list["AdminAction"]] = relationship(
        "AdminAction", 
        back_populates="admin_user",
        cascade="all, delete-orphan"
    )

    def has_permission(self, permission: str) -> bool:
        """Check if admin has specific permission."""
        if self.role == "super_admin":
            return True
        return permission in self.permissions

    def is_super_admin(self) -> bool:
        """Check if user is super admin."""
        return self.role == "super_admin"