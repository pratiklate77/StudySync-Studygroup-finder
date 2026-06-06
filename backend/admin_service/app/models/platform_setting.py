from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlatformSetting(Base):
    """Platform settings model for system configuration."""
    
    key: Mapped[str] = mapped_column(
        String(100), 
        unique=True, 
        nullable=False, 
        index=True
    )
    
    value: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    
    description: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    
    category: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        default="general",
        index=True,
    )  # general, payment, notification, etc.
    
    is_public: Mapped[bool] = mapped_column(
        default=False, 
        nullable=False
    )  # Whether setting can be read by non-admins
    
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), 
        nullable=True
    )  # Admin who last updated this setting