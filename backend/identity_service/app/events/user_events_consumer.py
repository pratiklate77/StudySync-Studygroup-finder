from __future__ import annotations
import asyncio
import json
import logging
from contextlib import suppress
from uuid import UUID

from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.kafka.producer import ResilientKafkaProducer
from app.services.tutor_service import TutorService

logger = logging.getLogger(__name__)


class UserEventsConsumer:
    """Consumes USER_EVENTS topic — reacts to TUTOR_VERIFIED events.

    Flow: Verification Service -> Kafka (USER_EVENTS) -> this consumer
      -> Update user role to TUTOR
      -> Set is_verified_tutor = True
      -> Publish TUTOR_VERIFIED to RATING_EVENTS for recommendation service
    """

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker,
        kafka_producer: ResilientKafkaProducer | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._kafka_producer = kafka_producer
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
                self._task = asyncio.create_task(self._run_loop(), name="identity-user-events-consumer")
                logger.info("UserEventsConsumer connected on startup attempt %d", attempt)
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

        logger.error("UserEventsConsumer unavailable after %d startup attempts", max_retries)
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

        try:
            user_id = UUID(str(user_id_raw))
        except ValueError:
            logger.warning("Invalid user_id in TUTOR_VERIFIED: %s", user_id_raw)
            return

        async with self._session_factory() as session:
            from app.repositories.user_repository import UserRepository
            from app.repositories.tutor_repository import TutorRepository
            from app.models.user import UserRole

            user_repo = UserRepository(session)
            tutor_repo = TutorRepository(session)

            user = await user_repo.get_by_id(user_id)
            if not user:
                logger.warning("User %s not found for TUTOR_VERIFIED", user_id)
                return

            # Update user role to tutor
            if user.role != UserRole.tutor:
                await user_repo.set_role(user, UserRole.tutor)
                logger.info("Updated user %s role to tutor", user_id)

            # Set verified tutor flag
            user.is_verified_tutor = True

            # Ensure tutor profile exists and mark verified
            profile = await tutor_repo.get_by_user_id(user_id)
            if profile:
                await tutor_repo.set_verified(profile, True)
            else:
                logger.warning("No tutor profile found for user %s to verify", user_id)

            await session.commit()
            logger.info("Successfully processed TUTOR_VERIFIED for user %s", user_id)

    async def _handle_tutor_rejected(self, data: dict) -> None:
        user_id_raw = data.get("user_id") or data.get("userId")
        if not user_id_raw:
            return

        try:
            user_id = UUID(str(user_id_raw))
        except ValueError:
            return

        async with self._session_factory() as session:
            from app.repositories.user_repository import UserRepository
            user_repo = UserRepository(session)
            user = await user_repo.get_by_id(user_id)
            if user:
                user.is_verified_tutor = False
                await session.commit()
                logger.info("TUTOR_REJECTED: cleared is_verified_tutor flag for user %s", user_id)
            else:
                logger.info("TUTOR_REJECTED received for user %s — user not found", user_id_raw)

    async def _handle_tutor_suspended(self, data: dict) -> None:
        user_id_raw = data.get("user_id") or data.get("userId")
        if not user_id_raw:
            return

        try:
            user_id = UUID(str(user_id_raw))
        except ValueError:
            return

        async with self._session_factory() as session:
            from app.repositories.user_repository import UserRepository
            from app.repositories.tutor_repository import TutorRepository
            user_repo = UserRepository(session)
            tutor_repo = TutorRepository(session)
            user = await user_repo.get_by_id(user_id)
            if user:
                user.is_verified_tutor = False
                profile = await tutor_repo.get_by_user_id(user_id)
                if profile:
                    await tutor_repo.set_verified(profile, False)
                await session.commit()
                logger.info("TUTOR_SUSPENDED: deactivated tutor flags for user %s", user_id)
            else:
                logger.info("TUTOR_SUSPENDED received for user %s — user not found", user_id_raw)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None