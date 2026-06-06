from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from uuid import UUID

from aiokafka import AIOKafkaConsumer

from app.core.config import Settings
from app.core.database import get_database
from app.repositories.session_repository import SessionRepository
from app.repositories.verified_tutor_repository import VerifiedTutorRepository

logger = logging.getLogger(__name__)


class PaymentEventsConsumer:
    """Consumes PAYMENT_SUCCESS from PAYMENT_EVENTS topic.
    Flow: Payment Service → Kafka → this consumer → SessionRepository.add_participant()
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self, retries: int | None = None, delay: float | None = None) -> bool:
        max_retries = retries if retries is not None else self._settings.kafka_startup_max_retries
        retry_delay = delay if delay is not None else self._settings.kafka_startup_retry_delay_seconds

        for attempt in range(1, max_retries + 1):
            consumer = AIOKafkaConsumer(
                self._settings.kafka_payment_events_topic,
                bootstrap_servers=self._settings.kafka_bootstrap_servers.split(","),
                group_id=f"{self._settings.kafka_consumer_group}-payment",
                client_id=f"{self._settings.kafka_client_id}-payment-consumer",
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
                self._task = asyncio.create_task(self._run_loop(), name="session-payment-consumer")
                logger.info("PaymentEventsConsumer connected on attempt %d", attempt)
                return True
            except Exception as exc:
                logger.warning("PaymentEventsConsumer startup attempt %d/%d failed: %s", attempt, max_retries, exc)
                try:
                    await consumer.stop()
                except Exception:
                    pass
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)

        logger.error("PaymentEventsConsumer unavailable after %d attempts", max_retries)
        return False

    async def _run_loop(self) -> None:
        assert self._consumer is not None
        try:
            async for msg in self._consumer:
                try:
                    data = msg.value
                    if not isinstance(data, dict):
                        continue
                    if data.get("event_type") != "PAYMENT_SUCCESS":
                        continue
                    session_id_raw = data.get("session_id")
                    student_id_raw = data.get("student_id")
                    if not session_id_raw or not student_id_raw:
                        continue
                    db = get_database()
                    repo = SessionRepository(db)
                    added = await repo.add_participant(
                        UUID(str(session_id_raw)),
                        UUID(str(student_id_raw)),
                    )
                    if added:
                        logger.info("PAYMENT_SUCCESS: student %s joined session %s", student_id_raw, session_id_raw)
                    else:
                        logger.warning("PAYMENT_SUCCESS: duplicate or full — student %s session %s", student_id_raw, session_id_raw)
                except Exception:
                    logger.exception("Failed processing PAYMENT_SUCCESS message")
        except asyncio.CancelledError:
            logger.info("PaymentEventsConsumer task cancelled")
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


class VerificationEventsConsumer:
    """Consumes TUTOR_APPLICATION_SUBMITTED from VERIFICATION_EVENTS topic.
    Flow: Identity Service → Kafka → this consumer → VerifiedTutorRepository.upsert_pending()
    Ensures pending tutors can create free sessions immediately after applying.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self, retries: int | None = None, delay: float | None = None) -> bool:
        max_retries = retries if retries is not None else self._settings.kafka_startup_max_retries
        retry_delay = delay if delay is not None else self._settings.kafka_startup_retry_delay_seconds

        for attempt in range(1, max_retries + 1):
            consumer = AIOKafkaConsumer(
                self._settings.kafka_verification_events_topic,
                bootstrap_servers=self._settings.kafka_bootstrap_servers.split(","),
                group_id=f"{self._settings.kafka_consumer_group}-verification",
                client_id=f"{self._settings.kafka_client_id}-verification-consumer",
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
                self._task = asyncio.create_task(self._run_loop(), name="session-verification-consumer")
                logger.info("VerificationEventsConsumer connected on attempt %d", attempt)
                return True
            except Exception as exc:
                logger.warning("VerificationEventsConsumer startup attempt %d/%d failed: %s", attempt, max_retries, exc)
                try:
                    await consumer.stop()
                except Exception:
                    pass
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)

        logger.error("VerificationEventsConsumer unavailable after %d attempts", max_retries)
        return False

    async def _run_loop(self) -> None:
        assert self._consumer is not None
        try:
            async for msg in self._consumer:
                try:
                    data = msg.value
                    if not isinstance(data, dict):
                        continue
                    event = data.get("event") or data.get("event_type")
                    if event == "TUTOR_APPLICATION_SUBMITTED":
                        user_id_raw = data.get("userId") or data.get("user_id")
                        if not user_id_raw:
                            continue
                        db = get_database()
                        repo = VerifiedTutorRepository(db)
                        await repo.upsert_pending(UUID(str(user_id_raw)))
                        logger.info("TUTOR_APPLICATION_SUBMITTED: pending record created for user %s", user_id_raw)
                except Exception:
                    logger.exception("Failed processing VERIFICATION_EVENTS message")
        except asyncio.CancelledError:
            logger.info("VerificationEventsConsumer task cancelled")
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


class UserEventsConsumer:
    """Consumes TUTOR_VERIFIED from USER_EVENTS topic.
    Flow: Identity Service → Kafka → this consumer → VerifiedTutorRepository.upsert()
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self, retries: int | None = None, delay: float | None = None) -> bool:
        max_retries = retries if retries is not None else self._settings.kafka_startup_max_retries
        retry_delay = delay if delay is not None else self._settings.kafka_startup_retry_delay_seconds

        for attempt in range(1, max_retries + 1):
            consumer = AIOKafkaConsumer(
                self._settings.kafka_user_events_topic,
                bootstrap_servers=self._settings.kafka_bootstrap_servers.split(","),
                group_id=f"{self._settings.kafka_consumer_group}-user",
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
                self._task = asyncio.create_task(self._run_loop(), name="session-user-consumer")
                logger.info("UserEventsConsumer connected on attempt %d", attempt)
                return True
            except Exception as exc:
                logger.warning("UserEventsConsumer startup attempt %d/%d failed: %s", attempt, max_retries, exc)
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
                    elif event_type == "TUTOR_SUSPENDED":
                        await self._handle_tutor_suspended(data)
                except Exception:
                    logger.exception("Failed processing USER_EVENTS message")
        except asyncio.CancelledError:
            logger.info("UserEventsConsumer task cancelled")
            raise

    async def _handle_tutor_verified(self, data: dict) -> None:
        user_id_raw = data.get("user_id") or data.get("userId")
        if not user_id_raw:
            logger.warning("TUTOR_VERIFIED event missing user_id")
            return
        db = get_database()
        repo = VerifiedTutorRepository(db)
        subjects = data.get("subjects")
        await repo.upsert_verified(UUID(str(user_id_raw)), subjects=subjects)
        logger.info("TUTOR_VERIFIED: marked user %s as verified tutor", user_id_raw)

    async def _handle_tutor_rejected(self, data: dict) -> None:
        user_id_raw = data.get("user_id") or data.get("userId")
        if not user_id_raw:
            logger.warning("TUTOR_REJECTED event missing user_id")
            return
        db = get_database()
        repo = VerifiedTutorRepository(db)
        await repo.mark_rejected(UUID(str(user_id_raw)))
        logger.info("TUTOR_REJECTED: marked user %s as rejected", user_id_raw)

    async def _handle_tutor_suspended(self, data: dict) -> None:
        user_id_raw = data.get("user_id") or data.get("userId")
        if not user_id_raw:
            logger.warning("TUTOR_SUSPENDED event missing user_id")
            return
        db = get_database()
        repo = VerifiedTutorRepository(db)
        await repo.mark_suspended(UUID(str(user_id_raw)))
        logger.info("TUTOR_SUSPENDED: marked user %s as suspended", user_id_raw)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None
