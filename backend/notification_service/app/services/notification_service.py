import logging
from typing import Any
from uuid import UUID

from jinja2 import Template as JinjaTemplate

from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.core.config import Settings
from app.models.notification import Notification
from app.repositories.notification_repository import (
    NotificationRepository,
    NotificationPreferenceRepository,
)
from app.schemas.notification import (
    NotificationListResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationRead,
    UnreadCountResponse,
)

logger = logging.getLogger("notification-service")


class NotificationService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
        ws_manager=None,
    ) -> None:
        self._session = session
        self._notif_repo = NotificationRepository(session)
        self._pref_repo = NotificationPreferenceRepository(session)
        self._redis = redis
        self._settings = settings
        self._ws_manager = ws_manager

    # ------------------------------------------------------------------
    # Notification CRUD
    # ------------------------------------------------------------------

    async def list_notifications(
        self,
        user_id: UUID,
        page: int,
        per_page: int,
        unread_only: bool,
        notification_type: str | None,
    ) -> NotificationListResponse:
        items, total = await self._notif_repo.list_for_user(
            user_id=user_id,
            page=page,
            per_page=per_page,
            unread_only=unread_only,
            notification_type=notification_type,
        )
        unread_count = await self.get_unread_count(user_id)

        return NotificationListResponse(
            items=[NotificationRead.model_validate(n) for n in items],
            total=total,
            page=page,
            per_page=per_page,
            unread_count=unread_count.count,
        )

    async def get_unread_count(self, user_id: UUID) -> UnreadCountResponse:
        cache_key = f"unread_count:{user_id}"
        cached = await self._redis.get(cache_key)
        if cached:
            return UnreadCountResponse(count=int(cached))

        count = await self._notif_repo.get_unread_count(user_id)
        await self._redis.setex(cache_key, self._settings.unread_count_cache_ttl_seconds, str(count))
        return UnreadCountResponse(count=count)

    async def mark_read(self, notification_id: UUID, user_id: UUID) -> bool:
        updated = await self._notif_repo.mark_read(notification_id, user_id)
        if updated:
            await self._session.commit()
            await self._redis.delete(f"unread_count:{user_id}")
        return updated

    async def mark_all_read(self, user_id: UUID) -> int:
        count = await self._notif_repo.mark_all_read(user_id)
        if count:
            await self._session.commit()
            await self._redis.delete(f"unread_count:{user_id}")
        return count

    async def delete_notification(self, notification_id: UUID, user_id: UUID) -> bool:
        deleted = await self._notif_repo.delete(notification_id, user_id)
        if deleted:
            await self._session.commit()
            await self._redis.delete(f"unread_count:{user_id}")
        return deleted

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------

    async def get_preferences(self, user_id: UUID) -> NotificationPreferenceResponse:
        pref = await self._pref_repo.get_by_user_id(user_id)
        if not pref:
            pref = await self._pref_repo.upsert(user_id=user_id)
            await self._session.commit()

        return NotificationPreferenceResponse.model_validate(pref)

    async def update_preferences(
        self,
        user_id: UUID,
        data: NotificationPreferenceUpdate,
    ) -> NotificationPreferenceResponse:
        update_data = data.model_dump(exclude_unset=True)
        pref = await self._pref_repo.upsert(user_id=user_id, **update_data)
        await self._session.commit()
        return NotificationPreferenceResponse.model_validate(pref)

    # ------------------------------------------------------------------
    # Event Processing
    # ------------------------------------------------------------------

    async def create_from_event(
        self,
        user_id: UUID,
        event_type: str,
        context: dict[str, Any],
        source_event_id: str,
    ) -> bool:
        """Process an incoming Kafka event: idempotency check → preference gate → render → persist → push."""
        # Idempotency Check
        existing = await self._notif_repo.get_by_source_event_id(source_event_id)
        if existing:
            return True

        # Preference Gate
        prefs = await self._pref_repo.get_by_user_id(user_id)
        if not prefs:
            prefs = await self._pref_repo.upsert(user_id=user_id)
            await self._session.flush()

        if not prefs.in_app_enabled or not prefs.notification_types.get(event_type, True):
            return False

        # Template Rendering
        tmpl = await self._notif_repo.get_active_template(event_type)
        if tmpl:
            title = JinjaTemplate(tmpl.title_template).render(**context)
            message = JinjaTemplate(tmpl.message_template).render(**context)
        else:
            title = event_type.replace("_", " ").title()
            message = f"Important update regarding {event_type.lower()}."

        # Persist
        notif = Notification(
            user_id=user_id,
            type=event_type,
            title=title,
            message=message,
            context=context,
            source_event_id=source_event_id,
            priority=context.get("priority", "normal"),
        )
        notif = await self._notif_repo.create(notif)
        await self._session.commit()

        # Real-time WebSocket Dispatch
        if self._ws_manager:
            ws_data = {
                "id": str(notif.id),
                "type": notif.type,
                "title": notif.title,
                "message": notif.message,
                "created_at": notif.created_at.isoformat(),
            }
            await self._ws_manager.send_personal_message(user_id, ws_data)

        await self._redis.delete(f"unread_count:{user_id}")
        return True

    async def record_failed_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        error: str,
    ) -> None:
        logger.error("Failed to process event %s: %s. Payload: %s", event_type, error, payload)