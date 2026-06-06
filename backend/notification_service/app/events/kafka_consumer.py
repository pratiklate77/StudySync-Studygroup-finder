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

# Maps event_type → user_id field name in the event payload
_USER_ID_FIELD: dict[str, str] = {
    "USER_REGISTERED": "user_id",
    "USER_CREATED": "user_id",
    "SESSION_CREATED": "host_id",
    "SESSION_CANCELLED": "host_id",
    "SESSION_REMINDER": "user_id",
    "GROUP_JOINED": "user_id",
    "GROUP_CREATED": "owner_id",
    "CHAT_MESSAGE_SENT": "sender_id",
    "PAYMENT_SUCCESS": "user_id",
    "PAYMENT_FAILED": "user_id",
    "TUTOR_VERIFIED": "user_id",
    "TUTOR_REJECTED": "user_id",
    "TUTOR_RECOMMENDED": "tutor_id",
    "VERIFICATION_SUBMITTED": "user_id",
    "VERIFICATION_APPROVED": "user_id",
    "VERIFICATION_REJECTED": "user_id",
    "SESSION_RATED": "tutorId",
    "RATING_SUBMITTED": "tutorId",
    "SESSION_STATUS_CHANGED": "user_id",
    "SESSION_STARTED": "user_id",
    "SESSION_ENROLLED": "user_id",
}


class NotificationEventConsumer:
    """
    Multi-topic Kafka consumer that routes events to the notification service.
    Uses a single consumer group across all topics for simplicity.
    """

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
            self._settings.kafka_recommendation_events_topic,
            self._settings.kafka_rating_events_topic,
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
                    event_type = data.get("event_type")
                    if not event_type:
                        continue

                    user_id_field = _USER_ID_FIELD.get(event_type)
                    if not user_id_field:
                        continue

                    raw_user_id = data.get(user_id_field)
                    if not raw_user_id:
                        continue

                    user_id = uuid.UUID(str(raw_user_id))
                    source_event_id = f"{event_type}:{data.get('request_id') or data.get('payment_id') or raw_user_id}:{msg.offset}"

                    async with self._session_factory() as session:
                        service = NotificationService(
                            session=session,
                            redis=self._redis,
                            settings=self._settings,
                            ws_manager=self._ws_manager,
                        )
                        await service.create_from_event(
                            user_id=user_id,
                            event_type=event_type,
                            context=data,
                            source_event_id=source_event_id,
                        )

                    logger.info("Processed %s for user %s", event_type, user_id)

                except Exception:
                    logger.exception("Failed processing event from topic %s offset %s", msg.topic, msg.offset)
                    try:
                        async with self._session_factory() as session:
                            service = NotificationService(
                                session=session,
                                redis=self._redis,
                                settings=self._settings,
                                ws_manager=self._ws_manager,
                            )
                            await service.record_failed_event(
                                event_type=data.get("event_type", "UNKNOWN"),
                                payload=data,
                                error="Consumer processing error",
                            )
                    except Exception:
                        logger.exception("Failed to record failed event")

        except asyncio.CancelledError:
            logger.info("NotificationEventConsumer task cancelled")
            raise

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
