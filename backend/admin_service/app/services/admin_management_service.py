from __future__ import annotations

import logging
import secrets
import string
import uuid
from typing import Any

from app.models.admin_user import AdminUser
from app.repositories.admin_repo import AdminRepository
from app.repositories.audit_repo import AuditRepository

logger = logging.getLogger(__name__)


class AdminManagementService:
    """Service for admin user management (CRUD, passwords)."""

    def __init__(
        self,
        admin_repo: AdminRepository,
        audit_repo: AuditRepository,
    ):
        self.admin_repo = admin_repo
        self.audit_repo = audit_repo

    async def get_admin_by_email(self, email: str) -> AdminUser | None:
        """Get admin by email."""
        return await self.admin_repo.get_by_email(email)

    async def get_admin_by_id(self, admin_id: uuid.UUID) -> AdminUser | None:
        """Get admin by ID."""
        return await self.admin_repo.get_by_id(admin_id)

    async def create_admin(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str,
        permissions: list[str],
        created_by: uuid.UUID,
    ) -> AdminUser:
        """Create new admin user."""
        admin = await self.admin_repo.create(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
            permissions=permissions,
        )

        await self.audit_repo.log_action(
            admin_id=created_by,
            action="ADMIN_CREATED",
            target_type="admin",
            target_id=str(admin.id),
            details={"email": email, "role": role},
        )
        return admin

    async def list_admins(
        self, skip: int = 0, limit: int = 50
    ) -> tuple[list[AdminUser], int]:
        """List all admin users."""
        return await self.admin_repo.list(skip=skip, limit=limit)

    async def update_admin(
        self,
        admin_id: uuid.UUID,
        update_data: dict[str, Any],
        updated_by: uuid.UUID,
    ) -> AdminUser:
        """Update admin user."""
        admin = await self.admin_repo.update(admin_id, update_data)

        await self.audit_repo.log_action(
            admin_id=updated_by,
            action="ADMIN_UPDATED",
            target_type="admin",
            target_id=str(admin_id),
            details=update_data,
        )
        return admin

    async def deactivate_admin(
        self, admin_id: uuid.UUID, deactivated_by: uuid.UUID
    ) -> None:
        """Deactivate admin user."""
        await self.admin_repo.deactivate(admin_id)

        await self.audit_repo.log_action(
            admin_id=deactivated_by,
            action="ADMIN_DEACTIVATED",
            target_type="admin",
            target_id=str(admin_id),
        )

    async def activate_admin(
        self, admin_id: uuid.UUID, activated_by: uuid.UUID
    ) -> None:
        """Activate admin user."""
        await self.admin_repo.activate(admin_id)

        await self.audit_repo.log_action(
            admin_id=activated_by,
            action="ADMIN_ACTIVATED",
            target_type="admin",
            target_id=str(admin_id),
        )

    async def change_password(
        self, admin_id: uuid.UUID, current_password: str, new_password: str
    ) -> bool:
        """Change admin password."""
        success = await self.admin_repo.change_password(
            admin_id, current_password, new_password
        )
        if success:
            await self.audit_repo.log_action(
                admin_id=admin_id,
                action="PASSWORD_CHANGED",
                target_type="admin",
                target_id=str(admin_id),
            )
        return success

    async def reset_admin_password(
        self, admin_id: uuid.UUID, reset_by: uuid.UUID
    ) -> str:
        """Reset admin password (super admin only), returns temp password."""
        alphabet = string.ascii_letters + string.digits
        temp_password = "".join(secrets.choice(alphabet) for _ in range(12))

        await self.admin_repo.reset_password(admin_id, temp_password)

        await self.audit_repo.log_action(
            admin_id=reset_by,
            action="PASSWORD_RESET",
            target_type="admin",
            target_id=str(admin_id),
        )
        return temp_password