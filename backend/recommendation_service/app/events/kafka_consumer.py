import asyncio
import json
import logging
from contextlib import suppress
from typing import TYPE_CHECKING

from aiokafka import AIOKafkaConsumer

from app.core.config import Settings
from app.services.recommendation_service import RecommendationService

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RatingEventsConsumer:
    def __init__(
        self,
        settings: Settings,
        session_factory,
        redis: "Redis | None",
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._redis = redis
        self._consumer = None
        self._task = None

    async def start(self, retries: int | None = None, delay: float | None = None) -> bool:
        max_retries = retries if retries is not None else self._settings.kafka_startup_max_retries
        retry_delay = delay if delay is not None else self._settings.kafka_startup_retry_delay_seconds

        for attempt in range(1, max_retries + 1):
            consumer = AIOKafkaConsumer(
                self._settings.kafka_rating_events_topic,
                bootstrap_servers=self._settings.kafka_bootstrap_servers.split(","),
                group_id=self._settings.kafka_consumer_group,
                client_id=f"{self._settings.kafka_client_id}-rating-consumer",
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
                self._task = asyncio.create_task(self._run_loop(), name="recommendation-rating-consumer")
                logger.info("Recommendation rating consumer connected on attempt %d", attempt)
                return True
            except Exception as exc:
                logger.warning(
                    "Recommendation rating consumer startup attempt %d/%d failed: %s",
                    attempt,
                    max_retries,
                    exc,
                )
                try:
                    await consumer.stop()
                except Exception:
                    logger.exception("Failed to stop Kafka consumer after startup error")
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)

        logger.error("Recommendation rating consumer unavailable after %d startup attempts", max_retries)
        return False

    async def _mark_processed(self, event_id: str | None, session_id: str | None, student_id: str | None) -> None:
        if self._redis is None:
            return
        key = event_id or (f"rating_event:{session_id}:{student_id}" if session_id and student_id else None)
        if key:
            await self._redis.setex(key, 60 * 60 * 24, "1")

    async def _is_duplicate(self, event_id: str | None, session_id: str | None, student_id: str | None) -> bool:
        if self._redis is None:
            return False
        key = event_id or (f"rating_event:{session_id}:{student_id}" if session_id and student_id else None)
        if key is None:
            return False
        return await self._redis.exists(key) == 1

    async def _run_loop(self) -> None:
        assert self._consumer is not None
        try:
            async for msg in self._consumer:
                try:
                    data = msg.value
                    if not isinstance(data, dict):
                        continue
                    event_type = data.get("event") or data.get("event_type")
                    if event_type != "SESSION_RATED":
                        continue
                    tutor_id = data.get("tutorId") or data.get("tutor_id")
                    score = data.get("rating") or data.get("score")
                    event_id = data.get("event_id")
                    session_id = data.get("sessionId")
                    student_id = data.get("studentId")
                    if tutor_id is None or score is None:
                        continue
                    if await self._is_duplicate(event_id, session_id, student_id):
                        logger.info(
                            "Skipping duplicate recommendation rating event event_id=%s sessionId=%s studentId=%s",
                            event_id,
                            session_id,
                            student_id,
                        )
                        continue
                    async with self._session_factory() as session:
                        service = RecommendationService(session, self._redis, self._settings)
                        updated = await service.apply_session_rating_event(
                            tutor_id=str(tutor_id),
                            score=int(score),
                            event_id=event_id,
                            session_id=session_id,
                            student_id=student_id,
                        )
                        if updated:
                            await self._mark_processed(event_id, session_id, student_id)
                except Exception:
                    logger.exception("Failed processing recommendation rating event")
        except asyncio.CancelledError:
            logger.info("Recommendation rating consumer task cancelled")
            raise

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None
