from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from aiokafka import AIOKafkaProducer

from app.core.config import Settings
from app.kafka.circuit_breaker import CircuitBreaker
from app.kafka.fallback_store import EventEnvelope, EventStore

logger = logging.getLogger(__name__)


class AdminKafkaProducer:
    """Kafka producer for admin events."""
    
    def __init__(
        self,
        *,
        settings: Settings,
        circuit_breaker: CircuitBreaker,
        fallback_store: EventStore,
    ) -> None:
        self._settings = settings
        self._circuit_breaker = circuit_breaker
        self._fallback_store = fallback_store
        self._producer: AIOKafkaProducer | None = None
        self._producer_lock = asyncio.Lock()

    async def start(self, retries: int | None = None, delay: float | None = None) -> bool:
        """Start the Kafka producer with retry logic."""
        max_retries = retries if retries is not None else self._settings.kafka_startup_max_retries
        retry_delay = delay if delay is not None else self._settings.kafka_startup_retry_delay_seconds

        for attempt in range(1, max_retries + 1):
            try:
                await self._ensure_producer()
                logger.info("Admin Kafka producer connected on startup attempt %d", attempt)
                return True
            except Exception as exc:
                await self._circuit_breaker.record_failure()
                logger.warning(
                    "Admin Kafka producer startup attempt %d/%d failed: %s",
                    attempt,
                    max_retries,
                    exc,
                )
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)

        logger.error("Admin Kafka producer unavailable after %d startup attempts", max_retries)
        return False

    async def stop(self) -> None:
        """Stop the Kafka producer."""
        async with self._producer_lock:
            if self._producer is not None:
                await self._producer.stop()
                self._producer = None

    async def publish_admin_event(
        self,
        *,
        event_type: str,
        admin_id: str,
        target_type: str | None = None,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Publish admin event to Kafka."""
        event_data = {
            "event_type": event_type,
            "admin_id": admin_id,
            "target_type": target_type,
            "target_id": target_id,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).timestamp(),
        }
        
        key = f"{event_type}:{target_id}" if target_id else event_type
        
        event = EventEnvelope(
            topic=self._settings.kafka_admin_events_topic,
            key=key.encode(),
            value=event_data,
        )
        
        return await self._publish_or_store(event, store_on_failure=True)

    async def publish_tutor_verified(self, *, user_id: str) -> bool:
        """Notify downstream services that a tutor was verified (USER_EVENTS)."""
        event_data = {
            "event": "TUTOR_VERIFIED",
            "event_type": "TUTOR_VERIFIED",
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        event = EventEnvelope(
            topic=self._settings.kafka_user_events_topic,
            key=user_id.encode(),
            value=event_data,
        )
        return await self._publish_or_store(event, store_on_failure=True)

    async def publish_user_restricted(self, *, user_id: str, reason: str | None = None) -> bool:
        event_data = {
            "event_type": "USER_RESTRICTED",
            "user_id": user_id,
            "reason": reason or "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        event = EventEnvelope(
            topic=self._settings.kafka_admin_events_topic,
            key=user_id.encode(),
            value=event_data,
        )
        return await self._publish_or_store(event, store_on_failure=True)

    async def publish_user_unrestricted(self, *, user_id: str) -> bool:
        event_data = {
            "event_type": "USER_UNRESTRICTED",
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        event = EventEnvelope(
            topic=self._settings.kafka_admin_events_topic,
            key=user_id.encode(),
            value=event_data,
        )
        return await self._publish_or_store(event, store_on_failure=True)

    async def retry_event(self, event: EventEnvelope) -> bool:
        """Retry publishing a failed event."""
        return await self._publish_or_store(event, store_on_failure=False)

    async def fallback_queue_size(self) -> int:
        """Get the size of the fallback queue."""
        return await self._fallback_store.size()

    async def _publish_or_store(self, event: EventEnvelope, *, store_on_failure: bool) -> bool:
        """Publish event or store in fallback queue."""
        if not await self._circuit_breaker.allow_request():
            if store_on_failure:
                await self._store_event(event, reason="circuit-open")
            return False

        try:
            producer = await self._ensure_producer()
            await asyncio.wait_for(
                producer.send_and_wait(
                    event.topic,
                    value=event.value,
                    key=event.key,
                ),
                timeout=self._settings.kafka_send_timeout_seconds,
            )
        except Exception as exc:
            await self._circuit_breaker.record_failure()
            await self._reset_producer()
            logger.warning(
                "Admin Kafka publish failed for event_id=%s topic=%s: %s",
                event.event_id,
                event.topic,
                exc,
            )
            if store_on_failure:
                await self._store_event(event, reason="publish-failed")
            return False

        await self._circuit_breaker.record_success()
        logger.info(
            "Admin Kafka publish succeeded for event_id=%s topic=%s",
            event.event_id,
            event.topic,
        )
        return True

    async def _store_event(self, event: EventEnvelope, *, reason: str) -> None:
        """Store event in fallback queue."""
        await self._fallback_store.put(event)
        logger.info(
            "Stored admin event in fallback queue event_id=%s topic=%s reason=%s",
            event.event_id,
            event.topic,
            reason,
        )

    async def _ensure_producer(self) -> AIOKafkaProducer:
        """Ensure Kafka producer is available."""
        async with self._producer_lock:
            if self._producer is not None:
                return self._producer

            producer = AIOKafkaProducer(
                bootstrap_servers=self._settings.kafka_bootstrap_servers.split(","),
                client_id=self._settings.kafka_client_id,
                acks="all",
                enable_idempotence=True,
                compression_type="gzip",
                linger_ms=10,
                request_timeout_ms=int(self._settings.kafka_send_timeout_seconds * 1000),
                value_serializer=lambda value: json.dumps(value).encode("utf-8"),
            )
            await asyncio.wait_for(
                producer.start(),
                timeout=self._settings.kafka_startup_timeout_seconds,
            )
            self._producer = producer
            return producer

    async def _reset_producer(self) -> None:
        """Reset the Kafka producer after failure."""
        async with self._producer_lock:
            producer = self._producer
            self._producer = None
        if producer is not None:
            try:
                await producer.stop()
            except Exception:
                logger.exception("Failed while stopping admin Kafka producer after publish error")