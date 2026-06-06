from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

import aiosmtplib
from aiokafka import AIOKafkaConsumer

from app.core.config import Settings

logger = logging.getLogger("email-worker")

_VERIFICATION_HTML = """\
<html><body>
<h2>Verify your StudySync email</h2>
<p>Click the link below to verify your email address. It expires in 24 hours.</p>
<p><a href="{verify_url}" style="padding:10px 20px;background:#4F46E5;color:white;text-decoration:none;border-radius:6px;">Verify Email</a></p>
<p>If you did not register, ignore this email.</p>
</body></html>
"""

_ENROLLMENT_HTML = """\
<html><body style="font-family:sans-serif;max-width:600px;margin:auto;">
<h2 style="color:#4F46E5;">You're enrolled in a session!</h2>
<table style="width:100%;border-collapse:collapse;">
  <tr><td style="padding:8px;font-weight:bold;">Session</td><td style="padding:8px;">{title}</td></tr>
  <tr style="background:#f9f9f9;"><td style="padding:8px;font-weight:bold;">Description</td><td style="padding:8px;">{description}</td></tr>
  <tr><td style="padding:8px;font-weight:bold;">Date &amp; Time</td><td style="padding:8px;">{scheduled_time}</td></tr>
  <tr style="background:#f9f9f9;"><td style="padding:8px;font-weight:bold;">Location</td><td style="padding:8px;">{address}</td></tr>
  <tr><td style="padding:8px;font-weight:bold;">Coordinates</td><td style="padding:8px;">{latitude}, {longitude}</td></tr>
  <tr style="background:#f9f9f9;"><td style="padding:8px;font-weight:bold;">Type</td><td style="padding:8px;">{session_type}</td></tr>
  <tr><td style="padding:8px;font-weight:bold;">Subjects</td><td style="padding:8px;">{subject_tags}</td></tr>
</table>
<p style="margin-top:20px;">A calendar invite (.ics) is attached — open it to add this session to your calendar.</p>
<p style="color:#888;font-size:12px;">StudySync — Learn Together</p>
</body></html>
"""


def _build_ics(title: str, description: str, address: str, scheduled_time: datetime, duration_minutes: int = 60) -> bytes:
    dt_start = scheduled_time.strftime("%Y%m%dT%H%M%SZ")
    dt_end = (scheduled_time + timedelta(minutes=duration_minutes)).strftime("%Y%m%dT%H%M%SZ")
    dt_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    uid = str(uuid.uuid4())
    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//StudySync//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{dt_stamp}\r\n"
        f"DTSTART:{dt_start}\r\n"
        f"DTEND:{dt_end}\r\n"
        f"SUMMARY:{title}\r\n"
        f"DESCRIPTION:{description}\r\n"
        f"LOCATION:{address}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    return ics.encode("utf-8")


class EmailWorker:
    """
    Kafka consumer that handles:
    - EMAIL_VERIFICATION_SENT  → sends verification email
    - SESSION_ENROLLED         → sends enrollment confirmation with .ics calendar attachment
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> bool:
        topics = [
            self._settings.kafka_user_events_topic,
            self._settings.kafka_session_events_topic,
        ]
        for attempt in range(1, self._settings.kafka_startup_max_retries + 1):
            consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=self._settings.kafka_bootstrap_servers.split(","),
                group_id="email-worker-group",
                client_id="email-worker",
                enable_auto_commit=True,
                auto_offset_reset="earliest",
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
            try:
                await asyncio.wait_for(consumer.start(), timeout=self._settings.kafka_startup_timeout_seconds)
                self._consumer = consumer
                self._task = asyncio.create_task(self._run(), name="email-worker")
                logger.info("EmailWorker connected on attempt %d", attempt)
                return True
            except Exception as exc:
                logger.warning("EmailWorker attempt %d/%d failed: %s", attempt, self._settings.kafka_startup_max_retries, exc)
                with suppress(Exception):
                    await consumer.stop()
                if attempt < self._settings.kafka_startup_max_retries:
                    await asyncio.sleep(self._settings.kafka_startup_retry_delay_seconds)

        logger.error("EmailWorker unavailable after retries")
        return False

    async def _run(self) -> None:
        assert self._consumer is not None
        try:
            async for msg in self._consumer:
                try:
                    data: dict = msg.value
                    event_type = data.get("event_type")
                    if event_type == "EMAIL_VERIFICATION_SENT":
                        await self._handle_verification(data)
                    elif event_type == "SESSION_ENROLLED":
                        await self._handle_enrollment(data)
                except Exception:
                    logger.exception("EmailWorker failed at offset %s", msg.offset)
        except asyncio.CancelledError:
            logger.info("EmailWorker task cancelled")
            raise

    async def _handle_verification(self, data: dict) -> None:
        email = data.get("email")
        token = data.get("token")
        if not email or not token:
            return
        verify_url = f"{self._settings.app_base_url}/api/v1/auth/verify-email?token={token}"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Verify your StudySync email"
        msg["From"] = self._settings.smtp_from_email
        msg["To"] = email
        msg.attach(MIMEText(_VERIFICATION_HTML.format(verify_url=verify_url), "html"))
        await self._smtp_send(msg, email)

    async def _handle_enrollment(self, data: dict) -> None:
        email = data.get("email")
        if not email:
            return

        title = data.get("title", "StudySync Session")
        description = data.get("description") or "No description provided."
        address = data.get("address") or "See coordinates below"
        latitude = data.get("latitude", "")
        longitude = data.get("longitude", "")
        session_type = data.get("session_type", "")
        subject_tags = ", ".join(data.get("subject_tags") or []) or "—"

        raw_time = data.get("scheduled_time")
        try:
            scheduled_time = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
        except Exception:
            scheduled_time = datetime.now(timezone.utc)

        formatted_time = scheduled_time.strftime("%A, %B %d %Y at %I:%M %p UTC")

        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"You're enrolled: {title}"
        msg["From"] = self._settings.smtp_from_email
        msg["To"] = email

        html_body = _ENROLLMENT_HTML.format(
            title=title,
            description=description,
            scheduled_time=formatted_time,
            address=address,
            latitude=latitude,
            longitude=longitude,
            session_type=session_type,
            subject_tags=subject_tags,
        )
        msg.attach(MIMEText(html_body, "html"))

        # Attach .ics calendar file
        ics_bytes = _build_ics(
            title=title,
            description=description,
            address=address,
            scheduled_time=scheduled_time.replace(tzinfo=None),
        )
        ics_part = MIMEBase("text", "calendar", method="REQUEST", name="session.ics")
        ics_part.set_payload(ics_bytes)
        encoders.encode_base64(ics_part)
        ics_part.add_header("Content-Disposition", "attachment", filename="session.ics")
        msg.attach(ics_part)

        await self._smtp_send(msg, email)

    async def _smtp_send(self, msg: MIMEMultipart, to_email: str) -> None:
        username = self._settings.smtp_username or None
        password = self._settings.smtp_password or None
        try:
            await aiosmtplib.send(
                msg,
                hostname=self._settings.smtp_host,
                port=self._settings.smtp_port,
                username=username,
                password=password,
                use_tls=self._settings.smtp_use_tls,
                start_tls=self._settings.smtp_start_tls,
            )
            logger.info("Email '%s' sent to %s", msg["Subject"], to_email)
        except Exception:
            logger.exception("Failed to send email to %s", to_email)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None


# Keep old name as alias for backward compat
EmailVerificationWorker = EmailWorker
