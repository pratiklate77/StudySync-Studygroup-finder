from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, select

from app.core.database import DatabaseManager
from app.core.security import get_password_hash, verify_password
from app.models.admin_user import AdminUser

logger = logging.getLogger(__name__)


class AdminRepository:
    """Repository for AdminUser CRUD operations (Admin DB)."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def get_by_id(self, admin_id: uuid.UUID) -> AdminUser | None:
        """Get admin by ID."""
        async with self.db_manager.AdminSessionLocal() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
            return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> AdminUser | None:
        """Get admin by email."""
        async with self.db_manager.AdminSessionLocal() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.email == email)
            )
            return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str,
        permissions: list[str],
    ) -> AdminUser:
        """Create new admin user."""
        async with self.db_manager.AdminSessionLocal() as session:
            admin = AdminUser(
                email=email,
                password_hash=get_password_hash(password),
                full_name=full_name,
                role=role,
                permissions=permissions,
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            await session.refresh(admin)
            return admin

    async def list(self, skip: int = 0, limit: int = 50) -> tuple[list[AdminUser], int]:
        """List admin users with pagination."""
        async with self.db_manager.AdminSessionLocal() as session:
            count_result = await session.execute(select(func.count(AdminUser.id)))
            total = count_result.scalar()

            result = await session.execute(
                select(AdminUser).offset(skip).limit(limit)
            )
            admins = result.scalars().all()
            return list(admins), total

    async def update(self, admin_id: uuid.UUID, update_data: dict[str, Any]) -> AdminUser | None:
        """Update admin user fields."""
        async with self.db_manager.AdminSessionLocal() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
            admin = result.scalar_one_or_none()
            if not admin:
                return None

            for field, value in update_data.items():
                if hasattr(admin, field):
                    setattr(admin, field, value)

            await session.commit()
            await session.refresh(admin)
            return admin

    async def deactivate(self, admin_id: uuid.UUID) -> AdminUser | None:
        """Deactivate admin user."""
        async with self.db_manager.AdminSessionLocal() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
            admin = result.scalar_one_or_none()
            if not admin:
                return None
            admin.is_active = False
            await session.commit()
            await session.refresh(admin)
            return admin

    async def activate(self, admin_id: uuid.UUID) -> AdminUser | None:
        """Activate admin user."""
        async with self.db_manager.AdminSessionLocal() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
            admin = result.scalar_one_or_none()
            if not admin:
                return None
            admin.is_active = True
            await session.commit()
            await session.refresh(admin)
            return admin

    async def change_password(self, admin_id: uuid.UUID, current_password: str, new_password: str) -> bool:
        """Change admin password after verifying current password."""
        async with self.db_manager.AdminSessionLocal() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
            admin = result.scalar_one_or_none()
            if not admin or not verify_password(current_password, admin.password_hash):
                return False

            admin.password_hash = get_password_hash(new_password)
            await session.commit()
            return True

    async def reset_password(self, admin_id: uuid.UUID, new_password: str) -> AdminUser | None:
        """Reset admin password (sets a new one)."""
        async with self.db_manager.AdminSessionLocal() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
            admin = result.scalar_one_or_none()
            if not admin:
                return None
            admin.password_hash = get_password_hash(new_password)
            await session.commit()
            await session.refresh(admin)
            return admin