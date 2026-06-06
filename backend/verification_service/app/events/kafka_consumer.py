from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress

from aiokafka import AIOKafkaConsumer

from app.core.config import Settings

logger = logging.getLogger(__name__)


class UserEventsConsumer:
    """Consumes USER_EVENTS topic — reacts to TUTOR_VERIFIED events."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> bool:
        for attempt in range(1, self._settings.kafka_startup_max_retries + 1):
            consumer = AIOKafkaConsumer(
                self._settings.kafka_user_events_topic,
                bootstrap_servers=self._settings.kafka_bootstrap_servers.split(","),
                group_id=f"{self._settings.kafka_client_id}-user-consumer",
                client_id=f"{self._settings.kafka_client_id}-user-consumer",
                enable_auto_commit=True,
                auto_offset_reset="earliest",
                session_timeout_ms=self._settings.kafka_consumer_session_timeout_ms,
                heartbeat_interval_ms=self._settings.kafka_consumer_heartbeat_interval_ms,
                request_timeout_ms=self._settings.kafka_consumer_request_timeout_ms,
                retry_backoff_ms=self._settings.kafka_consumer_retry_backoff_ms,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
            try:
                await asyncio.wait_for(
                    consumer.start(),
                    timeout=self._settings.kafka_startup_timeout_seconds,
                )
                self._consumer = consumer
                self._task = asyncio.create_task(self._run(), name="verification-user-consumer")
                logger.info("UserEventsConsumer connected on attempt %d", attempt)
                return True
            except Exception as exc:
                logger.warning("UserEventsConsumer attempt %d/%d failed: %s", attempt, self._settings.kafka_startup_max_retries, exc)
                try:
                    await consumer.stop()
                except Exception:
                    pass
                if attempt < self._settings.kafka_startup_max_retries:
                    await asyncio.sleep(self._settings.kafka_startup_retry_delay_seconds)

        logger.error("UserEventsConsumer unavailable after %d attempts", self._settings.kafka_startup_max_retries)
        return False

    async def _run(self) -> None:
        assert self._consumer is not None
        try:
            async for msg in self._consumer:
                try:
                    data = msg.value
                    if not isinstance(data, dict):
                        continue
                    event_type = data.get("event_type")
                    if event_type == "TUTOR_VERIFIED":
                        user_id = data.get("user_id")
                        logger.info("TUTOR_VERIFIED received for user %s — verification service notified", user_id)
                        # Future: cross-reference with pending verification requests
                        # and auto-approve or flag for admin review
                except Exception:
                    logger.exception("Error processing USER_EVENTS message")
        except asyncio.CancelledError:
            logger.info("UserEventsConsumer task cancelled")
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
