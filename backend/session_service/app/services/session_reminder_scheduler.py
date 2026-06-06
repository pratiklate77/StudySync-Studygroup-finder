from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.database import get_database
from app.events.kafka_producer import publish_session_starting_soon
from app.models.session import SessionStatus
from app.repositories.session_repository import SessionRepository

logger = logging.getLogger(__name__)

_REMINDER_WINDOW_MINUTES = 30
_POLL_INTERVAL_SECONDS = 60


class SessionReminderScheduler:
    """Polls MongoDB every minute for sessions starting in ~30 minutes and emits SESSION_STARTING_SOON."""

    def __init__(self, kafka_producer) -> None:
        self._producer = kafka_producer
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="session-reminder-scheduler")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await asyncio.sleep(_POLL_INTERVAL_SECONDS)
                await self._emit_reminders()
            except asyncio.CancelledError:
                logger.info("SessionReminderScheduler stopped")
                raise
            except Exception:
                logger.exception("SessionReminderScheduler error")

    async def _emit_reminders(self) -> None:
        now = datetime.now(timezone.utc)
        window_start = now + timedelta(minutes=_REMINDER_WINDOW_MINUTES - 1)
        window_end = now + timedelta(minutes=_REMINDER_WINDOW_MINUTES + 1)

        db = get_database()
        repo = SessionRepository(db)
        sessions = await repo.find_starting_between(window_start, window_end, status=SessionStatus.scheduled)

        for session in sessions:
            if not session.participants:
                continue
            try:
                await publish_session_starting_soon(
                    self._producer,
                    session_id=session.id,
                    title=session.title,
                    participant_ids=list(session.participants),
                    scheduled_time=session.scheduled_time,
                )
            except Exception:
                logger.exception("Failed to emit SESSION_STARTING_SOON for session %s", session.id)
