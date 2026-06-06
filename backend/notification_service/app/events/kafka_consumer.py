from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import suppress
from typing import Any

from aiokafka import AIOKafkaConsumer

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Events with a single direct recipient - maps event_type → user_id field
_SINGLE_RECIPIENT: dict[str, str] = {
    # Session
    "JOIN_REQUEST_ACCEPTED": "user_id",
    "JOIN_REQUEST_REJECTED": "user_id",
    # Payment
    "PAYMENT_SUCCESS": "user_id",
    "PAYMENT_FAILED": "user_id",
    # Admin
    "USER_RESTRICTED": "user_id",
    "USER_UNRESTRICTED": "user_id",
    # Group
    "GROUP_INVITATION": "invited_user_id",
    # Tutor verification (dual field names from verification_service)
    "TUTOR_APPROVED": "user_id",
    "TUTOR_REJECTED": "user_id",
}

# Events that fan-out to a list of recipients stored under a payload field
_MULTI_RECIPIENT: dict[str, str] = {
    "SESSION_STARTING_SOON": "participant_ids",
    "SESSION_CANCELLED": "participant_ids",
}


class NotificationEventConsumer:
    def __init__(self, settings: Settings, session_factory, redis, ws_manager=None) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._redis = redis
        self._ws_manager = ws_manager
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None

    def _topics(self) -> list[str]:
        return [
            self._settings.kafka_user_events_topic,
            self._settings.kafka_session_events_topic,
            self._settings.kafka_group_events_topic,
            self._settings.kafka_payment_events_topic,
            self._settings.kafka_verification_events_topic,
            self._settings.kafka_chat_events_topic,
            self._settings.kafka_admin_events_topic,
        ]

    async def start(self) -> bool:
        for attempt in range(1, self._settings.kafka_startup_max_retries + 1):
            consumer = AIOKafkaConsumer(
                *self._topics(),
                bootstrap_servers=self._settings.kafka_bootstrap_servers.split(","),
                group_id=self._settings.kafka_consumer_group,
                client_id=f"{self._settings.kafka_client_id}-consumer",
                enable_auto_commit=True,
                auto_offset_reset="earliest",
                session_timeout_ms=self._settings.kafka_consumer_session_timeout_ms,
                heartbeat_interval_ms=self._settings.kafka_consumer_heartbeat_interval_ms,
                request_timeout_ms=self._settings.kafka_consumer_request_timeout_ms,
                retry_backoff_ms=self._settings.kafka_consumer_retry_backoff_ms,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
            try:
                await asyncio.wait_for(consumer.start(), timeout=self._settings.kafka_startup_timeout_seconds)
                self._consumer = consumer
                self._task = asyncio.create_task(self._run(), name="notification-event-consumer")
                logger.info("NotificationEventConsumer connected on attempt %d", attempt)
                return True
            except Exception as exc:
                logger.warning("Consumer attempt %d/%d failed: %s", attempt, self._settings.kafka_startup_max_retries, exc)
                try:
                    await consumer.stop()
                except Exception:
                    pass
                if attempt < self._settings.kafka_startup_max_retries:
                    await asyncio.sleep(self._settings.kafka_startup_retry_delay_seconds)

        logger.error("NotificationEventConsumer unavailable after %d attempts", self._settings.kafka_startup_max_retries)
        return False

    async def _run(self) -> None:
        from app.services.notification_service import NotificationService
        assert self._consumer is not None
        try:
            async for msg in self._consumer:
                try:
                    data: dict[str, Any] = msg.value
                    if not isinstance(data, dict):
                        continue
                    event_type: str | None = data.get("event_type")
                    if not event_type:
                        continue

                    # Normalise TUTOR_VERIFIED → TUTOR_APPROVED for consistent naming
                    if event_type == "TUTOR_VERIFIED":
                        event_type = "TUTOR_APPROVED"
                        data = {**data, "event_type": "TUTOR_APPROVED"}

                    if event_type == "CHAT_MESSAGE_SENT":
                        await self._handle_chat_message(data, msg.offset)
                        continue

                    if event_type in _MULTI_RECIPIENT:
                        await self._handle_multi_recipient(event_type, data, msg.offset)
                        continue

                    if event_type in _SINGLE_RECIPIENT:
                        user_id_field = _SINGLE_RECIPIENT[event_type]
                        raw_uid = data.get(user_id_field) or data.get("userId")
                        if not raw_uid:
                            continue
                        user_id = uuid.UUID(str(raw_uid))
                        source_id = f"{event_type}:{data.get('request_id') or data.get('payment_id') or raw_uid}:{msg.offset}"
                        async with self._session_factory() as session:
                            svc = NotificationService(session=session, redis=self._redis, settings=self._settings, ws_manager=self._ws_manager)
                            await svc.create_from_event(user_id=user_id, event_type=event_type, context=data, source_event_id=source_id)

                except Exception:
                    logger.exception("Failed processing event from topic %s offset %s", msg.topic, msg.offset)

        except asyncio.CancelledError:
            logger.info("NotificationEventConsumer task cancelled")
            raise

    async def _handle_multi_recipient(self, event_type: str, data: dict[str, Any], offset: int) -> None:
        from app.services.notification_service import NotificationService
        participant_ids: list = data.get("participant_ids") or []
        for raw_uid in participant_ids:
            try:
                user_id = uuid.UUID(str(raw_uid))
                source_id = f"{event_type}:{data.get('session_id') or raw_uid}:{raw_uid}:{offset}"
                async with self._session_factory() as session:
                    svc = NotificationService(session=session, redis=self._redis, settings=self._settings, ws_manager=self._ws_manager)
                    await svc.create_from_event(user_id=user_id, event_type=event_type, context=data, source_event_id=source_id)
            except Exception:
                logger.exception("Failed processing %s for participant %s", event_type, raw_uid)

    async def _handle_chat_message(self, data: dict[str, Any], offset: int) -> None:
        """Only notify receivers who are offline (not in ws active connections)."""
        from app.services.notification_service import NotificationService
        receiver_ids: list = data.get("receiver_ids") or []
        for receiver_id_raw in receiver_ids:
            try:
                receiver_id = uuid.UUID(str(receiver_id_raw))
            except Exception:
                continue

            # Skip if user is currently connected via WebSocket
            if self._ws_manager and receiver_id in self._ws_manager.active_connections:
                continue

            source_id = f"CHAT_MESSAGE_RECEIVED:{data.get('message_id') or receiver_id_raw}:{receiver_id_raw}:{offset}"
            async with self._session_factory() as session:
                svc = NotificationService(session=session, redis=self._redis, settings=self._settings, ws_manager=self._ws_manager)
                await svc.create_from_event(
                    user_id=receiver_id,
                    event_type="CHAT_MESSAGE_RECEIVED",
                    context=data,
                    source_event_id=source_id,
                )

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
