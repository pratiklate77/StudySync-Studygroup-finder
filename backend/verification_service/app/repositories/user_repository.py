from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User


logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for accessing User records in the verification service database."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Fetch a User by its UUID.

        Returns ``None`` if the user does not exist or is inactive.
        """
        try:
            result = await self.db.execute(select(User).where(User.id == user_id))
            user: Optional[User] = result.scalar_one_or_none()
            return user
        except Exception as exc:
            logger.error("Error fetching user %s: %s", user_id, exc)
            raise
