from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select, update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationTemplate
from app.models.preference import NotificationPreference


class NotificationRepository:
    """Data access layer for Notification model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, notification: Notification) -> Notification:
        self._session.add(notification)
        await self._session.flush()
        await self._session.refresh(notification)
        return notification

    async def get_by_id(self, notification_id: uuid.UUID) -> Optional[Notification]:
        result = await self._session.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        return result.scalar_one_or_none()

    async def get_by_source_event_id(self, source_event_id: str) -> Optional[Notification]:
        result = await self._session.execute(
            select(Notification).where(Notification.source_event_id == source_event_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: UUID,
        page: int = 1,
        per_page: int = 20,
        unread_only: bool = False,
        notification_type: Optional[str] = None,
    ) -> tuple[list[Notification], int]:
        base = select(Notification).where(Notification.user_id == user_id)
        count_base = select(func.count()).select_from(Notification).where(Notification.user_id == user_id)

        if unread_only:
            base = base.where(Notification.is_read == False)
            count_base = count_base.where(Notification.is_read == False)
        if notification_type:
            base = base.where(Notification.type == notification_type)
            count_base = count_base.where(Notification.type == notification_type)

        total = (await self._session.execute(count_base)).scalar() or 0
        offset = (page - 1) * per_page
        items = (
            (
                await self._session.execute(
                    base.order_by(Notification.created_at.desc()).offset(offset).limit(per_page)
                )
            )
            .scalars()
            .all()
        )
        return list(items), total

    async def get_unread_count(self, user_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Notification).where(
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
        )
        return result.scalar() or 0

    async def get_new_count(self, user_id: UUID, since: datetime | None) -> int:
        """Count notifications received after last_notification_seen_at."""
        from datetime import timezone
        q = select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        if since is not None:
            aware = since.replace(tzinfo=timezone.utc) if since.tzinfo is None else since
            q = q.where(Notification.created_at > aware)
        return (await self._session.execute(q)).scalar() or 0

    async def mark_read(self, notification_id: uuid.UUID, user_id: UUID) -> bool:
        from datetime import datetime, timezone

        result = await self._session.execute(
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        return result.rowcount > 0

    async def mark_all_read(self, user_id: UUID) -> int:
        from datetime import datetime, timezone

        result = await self._session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        return result.rowcount

    async def delete(self, notification_id: uuid.UUID, user_id: UUID) -> bool:
        result = await self._session.execute(
            sa_delete(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        )
        return result.rowcount > 0

    async def get_active_template(self, event_type: str) -> Optional[NotificationTemplate]:
        result = await self._session.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.event_type == event_type,
                NotificationTemplate.is_active == True,
            )
        )
        return result.scalar_one_or_none()


class NotificationPreferenceRepository:
    """Data access layer for NotificationPreference model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: UUID) -> Optional[NotificationPreference]:
        return await self._session.get(NotificationPreference, user_id)

    async def upsert(self, user_id: UUID, **kwargs: Any) -> NotificationPreference:
        pref = await self._session.get(NotificationPreference, user_id)
        if not pref:
            pref = NotificationPreference(user_id=user_id, **kwargs)
            self._session.add(pref)
        else:
            for k, v in kwargs.items():
                if v is not None:
                    setattr(pref, k, v)
        await self._session.flush()
        await self._session.refresh(pref)
        return pref

    async def update_seen_at(self, user_id: UUID, seen_at: datetime) -> None:
        pref = await self._session.get(NotificationPreference, user_id)
        if not pref:
            pref = NotificationPreference(user_id=user_id, last_notification_seen_at=seen_at)
            self._session.add(pref)
        else:
            pref.last_notification_seen_at = seen_at
        await self._session.flush()