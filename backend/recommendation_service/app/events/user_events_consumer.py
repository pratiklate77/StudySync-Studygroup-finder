from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from uuid import UUID

from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.models.tutor_metric import TutorMetric
from app.services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)


class UserEventsConsumer:
    """Consumes USER_EVENTS topic — reacts to TUTOR_VERIFIED and TUTOR_REJECTED events.

    - TUTOR_VERIFIED: Marks tutor as verified in recommendation metrics
    - TUTOR_REJECTED: Removes tutor from recommendation pool
    """

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> bool:
        max_retries = self._settings.kafka_startup_max_retries
        retry_delay = self._settings.kafka_startup_retry_delay_seconds

        for attempt in range(1, max_retries + 1):
            consumer = AIOKafkaConsumer(
                self._settings.kafka_user_events_topic,
                bootstrap_servers=self._settings.kafka_bootstrap_servers.split(","),
                group_id=f"{self._settings.kafka_client_id}-user-events",
                client_id=f"{self._settings.kafka_client_id}-user-events-consumer",
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
                self._task = asyncio.create_task(self._run_loop(), name="rec-user-events-consumer")
                logger.info("UserEventsConsumer connected on attempt %d", attempt)
                return True
            except Exception as exc:
                logger.warning(
                    "UserEventsConsumer startup attempt %d/%d failed: %s",
                    attempt,
                    max_retries,
                    exc,
                )
                try:
                    await consumer.stop()
                except Exception:
                    pass
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)

        logger.error("UserEventsConsumer unavailable after %d attempts", max_retries)
        return False

    async def _run_loop(self) -> None:
        assert self._consumer is not None
        try:
            async for msg in self._consumer:
                try:
                    data = msg.value
                    if not isinstance(data, dict):
                        continue

                    event_type = data.get("event_type") or data.get("event")
                    if event_type == "TUTOR_VERIFIED":
                        await self._handle_tutor_verified(data)
                    elif event_type == "TUTOR_REJECTED":
                        await self._handle_tutor_rejected(data)
                except Exception:
                    logger.exception("Failed processing USER_EVENTS message")
        except asyncio.CancelledError:
            logger.info("UserEventsConsumer task cancelled")
            raise

    async def _handle_tutor_verified(self, data: dict) -> None:
        user_id_raw = data.get("user_id") or data.get("userId")
        if not user_id_raw:
            return

        try:
            tutor_id = UUID(str(user_id_raw))
        except ValueError:
            logger.warning("Invalid user_id in TUTOR_VERIFIED: %s", user_id_raw)
            return

        async with self._session_factory() as session:
            try:
                existing = await session.get(TutorMetric, tutor_id)
                if existing is not None:
                    existing.is_verified = True
                else:
                    # Create a minimal entry so the tutor can be recommended
                    metric = TutorMetric(
                        tutor_id=tutor_id,
                        is_verified=True,
                        average_rating=0.0,
                        total_reviews=0,
                        sessions_completed=0,
                        activity_score=0.0,
                        subjects=[],
                    )
                    session.add(metric)

                await session.commit()
                logger.info("Marked tutor %s as verified in recommendation metrics", tutor_id)
            except Exception:
                await session.rollback()
                logger.exception("Failed to mark tutor %s as verified", tutor_id)

    async def _handle_tutor_rejected(self, data: dict) -> None:
        user_id_raw = data.get("user_id") or data.get("userId")
        if not user_id_raw:
            return

        try:
            tutor_id = UUID(str(user_id_raw))
        except ValueError:
            return

        async with self._session_factory() as session:
            try:
                existing = await session.get(TutorMetric, tutor_id)
                if existing is not None:
                    existing.is_verified = False
                    existing.recommendation_score = -1.0  # Effectively exclude from recommendations
                    await session.commit()
                    logger.info("Marked tutor %s as rejected in recommendation metrics", tutor_id)
            except Exception:
                await session.rollback()
                logger.exception("Failed to mark tutor %s as rejected", tutor_id)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None