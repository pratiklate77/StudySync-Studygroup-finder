from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models.enums import DocumentType, VerificationStatus
from app.models.tutor_verification_request import TutorVerificationRequest
from app.models.verification_document import VerificationDocument

logger = logging.getLogger(__name__)


class VerificationEventsConsumer:
    """
    Consumes VERIFICATION_EVENTS topic.

    On TUTOR_APPLICATION_SUBMITTED:
      - Creates a TutorVerificationRequest record in the verification DB
      - Creates VerificationDocument records for each uploaded document
      - This allows the verification service's admin endpoints to list/review applications
    """

    def __init__(
        self,
        settings: Settings,
        db_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._settings = settings
        self._consumer = None
        self._task: asyncio.Task | None = None
        self._db_session_factory = db_session_factory

    async def start(self) -> bool:
        try:
            from aiokafka import AIOKafkaConsumer
        except ImportError:
            logger.error("aiokafka not installed, cannot start VerificationEventsConsumer")
            return False

        for attempt in range(1, self._settings.kafka_startup_max_retries + 1):
            consumer = AIOKafkaConsumer(
                self._settings.kafka_verification_events_topic,
                bootstrap_servers=self._settings.kafka_bootstrap_servers.split(","),
                group_id=f"{self._settings.kafka_client_id}-verification-events",
                client_id=f"{self._settings.kafka_client_id}-verification-events",
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
                self._task = asyncio.create_task(
                    self._run(), name="verification-events-consumer"
                )
                logger.info(
                    "VerificationEventsConsumer connected on attempt %d", attempt
                )
                return True
            except Exception as exc:
                logger.warning(
                    "VerificationEventsConsumer attempt %d/%d failed: %s",
                    attempt,
                    self._settings.kafka_startup_max_retries,
                    exc,
                )
                try:
                    await consumer.stop()
                except Exception:
                    pass
                if attempt < self._settings.kafka_startup_max_retries:
                    await asyncio.sleep(self._settings.kafka_startup_retry_delay_seconds)

        logger.error(
            "VerificationEventsConsumer unavailable after %d attempts",
            self._settings.kafka_startup_max_retries,
        )
        return False

    async def _run(self) -> None:
        assert self._consumer is not None
        try:
            async for msg in self._consumer:
                try:
                    data = msg.value
                    if not isinstance(data, dict):
                        continue

                    event = data.get("event")
                    if event == "TUTOR_APPLICATION_SUBMITTED":
                        await self._handle_tutor_application_submitted(data)

                except Exception:
                    logger.exception("Error processing VERIFICATION_EVENTS message")
        except asyncio.CancelledError:
            logger.info("VerificationEventsConsumer task cancelled")
            raise

    async def _handle_tutor_application_submitted(self, data: dict) -> None:
        """Create a TutorVerificationRequest from the event data."""
        user_id_str = data.get("userId")
        bio = data.get("bio", "")
        subjects = data.get("subjects", [])
        hourly_rate = data.get("hourly_rate", "0")
        documents = data.get("documents", [])

        if not user_id_str:
            logger.warning("TUTOR_APPLICATION_SUBMITTED event missing userId")
            return

        try:
            user_id = UUID(user_id_str)
        except ValueError:
            logger.warning("Invalid userId in event: %s", user_id_str)
            return

        # Use a new session for each event
        async with self._db_session_factory() as db:
            async with db.begin():
                # Check for existing pending request
                existing = await db.execute(
                    select(TutorVerificationRequest).where(
                        TutorVerificationRequest.user_id == user_id,
                        TutorVerificationRequest.status.in_(
                            [VerificationStatus.PENDING, VerificationStatus.UNDER_REVIEW]
                        ),
                    )
                )
                if existing.scalar_one_or_none():
                    logger.info(
                        "Pending verification request already exists for user %s, skipping",
                        user_id,
                    )
                    return

                # Create verification request
                subjects_str = ", ".join(subjects) if isinstance(subjects, list) else subjects

                try:
                    hourly_rate_float = float(hourly_rate)
                except (ValueError, TypeError):
                    hourly_rate_float = 0.0

                verification_request = TutorVerificationRequest(
                    user_id=user_id,
                    bio=bio,
                    subjects=subjects_str,
                    hourly_rate=hourly_rate_float,
                    status=VerificationStatus.PENDING,
                )
                db.add(verification_request)
                await db.flush()

                # Create document records
                docs_to_add = []
                for doc in documents:
                    doc_type = doc.get("document_type", "UNKNOWN")
                    file_name = doc.get("file_name", "")
                    file_url = doc.get("file_url", "")

                    # Map the identity service's document type strings to our enum
                    try:
                        doc_type_enum = DocumentType(doc_type)
                    except ValueError:
                        doc_type_enum = DocumentType.CERTIFICATE

                    docs_to_add.append(
                        VerificationDocument(
                            request_id=verification_request.id,
                            file_name=file_name,
                            file_url=file_url,
                            document_type=doc_type_enum.value,
                        )
                    )

                if docs_to_add:
                    db.add_all(docs_to_add)

                logger.info(
                    "Created TutorVerificationRequest for user %s from event (request_id=%s, docs=%d)",
                    user_id,
                    verification_request.id,
                    len(docs_to_add),
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