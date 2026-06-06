from __future__ import annotations

import logging
import uuid
from datetime import datetime, date

from sqlalchemy import text

from app.core.database import DatabaseManager
from app.schemas.user import UserSummary

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for user operations against Identity DB."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def list_users(
        self,
        page: int = 1,
        per_page: int = 20,
        role: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[UserSummary], int]:
        """Get paginated list of users from Identity DB."""
        async with self.db_manager.IdentitySessionLocal() as session:
            conditions = ["1=1"]
            params: dict[str, object] = {}

            if role:
                conditions.append("role = :role")
                params["role"] = role
            if is_active is not None:
                conditions.append("is_active = :is_active")
                params["is_active"] = is_active
            if search:
                conditions.append("email ILIKE :search")
                params["search"] = f"%{search}%"

            where = " AND ".join(conditions)

            count_result = await session.execute(
                text(f"SELECT COUNT(*) FROM users WHERE {where}"), params
            )
            total = count_result.scalar() or 0

            offset = (page - 1) * per_page
            params["limit"] = per_page
            params["offset"] = offset
            rows = await session.execute(
                text(
                    f"SELECT id, email, role, is_active, is_verified_tutor, created_at "
                    f"FROM users WHERE {where} ORDER BY created_at DESC "
                    f"LIMIT :limit OFFSET :offset"
                ),
                params,
            )
            users = [
                UserSummary(
                    id=r.id,
                    email=r.email,
                    full_name=None,
                    role=r.role,
                    is_active=r.is_active,
                    is_verified=r.is_verified_tutor or False,
                    created_at=r.created_at,
                    last_login=None,
                )
                for r in rows.fetchall()
            ]
            return users, total

    async def get_user_details(self, user_id: uuid.UUID) -> dict | None:
        """Get detailed user info from Identity DB."""
        async with self.db_manager.IdentitySessionLocal() as session:
            result = await session.execute(
                text(
                    "SELECT id, email, role, is_active, is_verified_tutor, created_at, updated_at, last_login "
                    "FROM users WHERE id = :user_id"
                ),
                {"user_id": user_id},
            )
            row = result.fetchone()
            if not row:
                return None
            return {
                "id": row.id,
                "email": row.email,
                "full_name": None,
                "role": row.role,
                "is_active": row.is_active,
                "is_verified": row.is_verified_tutor or False,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "last_login": row.last_login,
            }

    async def suspend_user(self, user_id: uuid.UUID) -> bool:
        """Suspend a user account."""
        async with self.db_manager.IdentitySessionLocal() as session:
            result = await session.execute(
                text("UPDATE users SET is_active = false WHERE id = :user_id"),
                {"user_id": user_id},
            )
            if result.rowcount == 0:
                return False
            await session.commit()
            return True

    async def activate_user(self, user_id: uuid.UUID) -> bool:
        """Activate a user account."""
        async with self.db_manager.IdentitySessionLocal() as session:
            result = await session.execute(
                text("UPDATE users SET is_active = true WHERE id = :user_id"),
                {"user_id": user_id},
            )
            if result.rowcount == 0:
                return False
            await session.commit()
            return True

    async def verify_tutor(self, user_id: uuid.UUID) -> bool:
        """Mark a tutor verified in Identity DB."""
        async with self.db_manager.IdentitySessionLocal() as session:
            profile = await session.execute(
                text("SELECT id FROM tutor_profiles WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            if profile.first() is None:
                return False

            await session.execute(
                text("UPDATE tutor_profiles SET is_verified = true WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            await session.execute(
                text("UPDATE users SET role = 'tutor', is_verified_tutor = true WHERE id = :user_id"),
                {"user_id": user_id},
            )
            await session.commit()
            return True

    # ── Metrics helpers ──────────────────────────────────────────────

    async def count_total_users(self) -> int:
        """Get total number of users."""
        async with self.db_manager.IdentitySessionLocal() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            return result.scalar() or 0

    async def count_total_tutors(self) -> int:
        """Get total number of tutors."""
        async with self.db_manager.IdentitySessionLocal() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM users WHERE role = 'tutor'")
            )
            return result.scalar() or 0

    async def count_total_students(self) -> int:
        """Get total number of students."""
        async with self.db_manager.IdentitySessionLocal() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM users WHERE role = 'student'")
            )
            return result.scalar() or 0

    async def count_active_users_today(self) -> int:
        """Get number of users active today."""
        today = date.today()
        async with self.db_manager.IdentitySessionLocal() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM users WHERE DATE(last_login) = :today"),
                {"today": today},
            )
            return result.scalar() or 0

    async def count_pending_verifications(self) -> int:
        """Get count of pending verification requests."""
        try:
            async with self.db_manager.IdentitySessionLocal() as session:
                result = await session.execute(
                    text("SELECT COUNT(*) FROM verification_requests WHERE status = 'PENDING'")
                )
                return int(result.scalar() or 0)
        except Exception:
            return 0