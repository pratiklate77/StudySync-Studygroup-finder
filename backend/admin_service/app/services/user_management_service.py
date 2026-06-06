from __future__ import annotations

import logging
import uuid

from app.repositories.audit_repo import AuditRepository
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserSummary

logger = logging.getLogger(__name__)


class UserManagementService:
    """Service for user lifecycle management operations."""

    def __init__(
        self,
        user_repo: UserRepository,
        audit_repo: AuditRepository,
        kafka_producer=None,
    ):
        self.user_repo = user_repo
        self.audit_repo = audit_repo
        self.kafka_producer = kafka_producer

    async def get_users_list(
        self,
        page: int = 1,
        per_page: int = 20,
        role: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[UserSummary], int]:
        """Get paginated list of users."""
        return await self.user_repo.list_users(
            page=page,
            per_page=per_page,
            role=role,
            is_active=is_active,
            search=search,
        )

    async def get_user_details(self, user_id: uuid.UUID) -> dict | None:
        """Get detailed user information."""
        return await self.user_repo.get_user_details(user_id)

    async def suspend_user(
        self,
        user_id: uuid.UUID,
        admin_id: uuid.UUID,
        reason: str | None = None,
    ) -> bool:
        """Suspend a user account."""
        success = await self.user_repo.suspend_user(user_id)
        if not success:
            return False

        await self.audit_repo.log_action(
            admin_id=admin_id,
            action="USER_SUSPENDED",
            target_type="user",
            target_id=str(user_id),
            reason=reason,
        )
        if self.kafka_producer:
            await self.kafka_producer.publish_user_restricted(user_id=str(user_id), reason=reason)
        return True

    async def activate_user(
        self,
        user_id: uuid.UUID,
        admin_id: uuid.UUID,
        reason: str | None = None,
    ) -> bool:
        """Activate a user account."""
        success = await self.user_repo.activate_user(user_id)
        if not success:
            return False

        await self.audit_repo.log_action(
            admin_id=admin_id,
            action="USER_ACTIVATED",
            target_type="user",
            target_id=str(user_id),
            reason=reason,
        )
        if self.kafka_producer:
            await self.kafka_producer.publish_user_unrestricted(user_id=str(user_id))
        return True