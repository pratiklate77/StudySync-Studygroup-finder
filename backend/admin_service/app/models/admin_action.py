from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.admin_user import AdminUser


class AdminAction(Base):
    """Admin action model for audit logging."""
    
    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_user.id"),
        nullable=False,
        index=True,
    )
    
    action: Mapped[str] = mapped_column(
        String(100), 
        nullable=False,
        index=True,
    )  # suspend_user, activate_user, approve_verification, etc.
    
    target_type: Mapped[str | None] = mapped_column(
        String(50), 
        nullable=True,
        index=True,
    )  # user, tutor, session, payment, etc.
    
    target_id: Mapped[str | None] = mapped_column(
        String(255), 
        nullable=True,
        index=True,
    )  # ID of the target entity
    
    details: Mapped[dict] = mapped_column(
        JSONB, 
        nullable=False, 
        default=dict
    )  # Additional action details
    
    reason: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )  # Reason for the action
    
    ip_address: Mapped[str | None] = mapped_column(
        String(45), 
        nullable=True
    )  # Admin's IP address
    
    user_agent: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )  # Admin's browser/client info
    
    # Relationships
    admin_user: Mapped["AdminUser"] = relationship(
        "AdminUser", 
        back_populates="actions"
    )