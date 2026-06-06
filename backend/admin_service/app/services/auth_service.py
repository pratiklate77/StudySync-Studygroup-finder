from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.core.security import create_access_token, get_password_hash, verify_password
from app.kafka.producer import AdminKafkaProducer
from app.models.admin_user import AdminUser
from app.repositories.admin_repo import AdminRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.auth import AdminLoginResponse, AdminProfile

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication and admin profile service."""

    def __init__(
        self,
        admin_repo: AdminRepository,
        audit_repo: AuditRepository,
        kafka_producer: AdminKafkaProducer,
        settings: Settings,
    ):
        self.admin_repo = admin_repo
        self.audit_repo = audit_repo
        self.kafka_producer = kafka_producer
        self.settings = settings

    async def ensure_super_admin(self) -> None:
        """Create super admin user if not exists."""
        admin = await self.admin_repo.get_by_email(self.settings.super_admin_email)
        if not admin:
            admin = await self.admin_repo.create(
                email=self.settings.super_admin_email,
                password=self.settings.super_admin_password,
                full_name="Super Administrator",
                role="super_admin",
                permissions=[],
            )
            logger.info("Super admin created: %s", self.settings.super_admin_email)

    async def authenticate_admin(self, email: str, password: str) -> AdminLoginResponse | None:
        """Authenticate admin user and return login response."""
        admin = await self.admin_repo.get_by_email(email)
        if not admin or not verify_password(password, admin.password_hash):
            return None

        # Update login info via repo
        updated = await self.admin_repo.update(
            admin.id,
            {
                "last_login": datetime.utcnow(),
                "login_count": admin.login_count + 1,
            },
        )
        if not updated:
            return None

        # Create access token
        token_data = {
            "sub": str(admin.id),
            "email": admin.email,
            "role": admin.role,
        }
        access_token = create_access_token(token_data)

        return AdminLoginResponse(
            access_token=access_token,
            admin_id=admin.id,
            email=admin.email,
            full_name=admin.full_name,
            role=admin.role,
            permissions=admin.permissions,
        )

    async def get_admin_profile(self, admin_id: uuid.UUID) -> AdminProfile | None:
        """Get admin profile by ID."""
        admin = await self.admin_repo.get_by_id(admin_id)
        if not admin:
            return None
        return AdminProfile.model_validate(admin)

    async def log_admin_action(
        self,
        admin_id: uuid.UUID,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
        reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log admin action for audit trail and broadcast event."""
        await self.audit_repo.log_action(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Broadcast admin event via Kafka
        await self.kafka_producer.publish_admin_event(
            event_type=action,
            admin_id=str(admin_id),
            target_type=target_type,
            target_id=target_id,
            details=details,
        )