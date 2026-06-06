from __future__ import annotations

import asyncio
import logging

from app.kafka.fallback_store import EventEnvelope, EventStore
from app.kafka.producer import AdminKafkaProducer

logger = logging.getLogger(__name__)


class AdminKafkaRetryWorker:
    def __init__(
        self,
        *,
        producer: AdminKafkaProducer,
        fallback_store: EventStore,
        base_delay: float,
        max_delay: float,
    ) -> None:
        self._producer = producer
        self._fallback_store = fallback_store
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        logger.info("Admin Kafka retry worker started")
        while not self._stop_event.is_set():
            event = await self._next_event()
            if event is None:
                break

            success = await self._producer.retry_event(event)
            if success:
                logger.info(
                    "Retried admin event successfully event_id=%s retries=%d",
                    event.event_id,
                    event.retry_count,
                )
                continue

            event.retry_count += 1
            delay = min(self._base_delay * (2 ** max(0, event.retry_count - 1)), self._max_delay)
            logger.warning(
                "Admin retry failed for event_id=%s retry_count=%d next_attempt_in=%.2fs",
                event.event_id,
                event.retry_count,
                delay,
            )
            await asyncio.sleep(delay)
            await self._fallback_store.requeue(event)

        logger.info("Admin Kafka retry worker stopped")

    async def stop(self) -> None:
        self._stop_event.set()
        await self._fallback_store.put(
            EventEnvelope(
                topic="__admin_retry_worker_shutdown__",
                key=b"",
                value={},
            )
        )

    async def _next_event(self) -> EventEnvelope | None:
        event = await self._fallback_store.get()
        if self._stop_event.is_set() and event.topic == "__admin_retry_worker_shutdown__":
            return None
        if event.topic == "__admin_retry_worker_shutdown__":
            return await self._next_event()
        return event