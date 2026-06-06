from __future__ import annotations

import logging
from uuid import UUID

from app.core.config import Settings
from app.kafka.producer import ResilientKafkaProducer

logger = logging.getLogger(__name__)


async def publish_user_created(
    producer: ResilientKafkaProducer,
    settings: Settings,
    *,
    user_id: UUID,
    email: str,
    role: str,
) -> bool:
    published = await producer.publish(
        topic=settings.kafka_user_events_topic,
        value={
            "event_type": "USER_CREATED",
            "user_id": str(user_id),
            "email": email,
            "role": role,
        },
        key=str(user_id).encode("utf-8"),
    )
    if published:
        logger.info("Published USER_CREATED user_id=%s", user_id)
    else:
        logger.warning("Queued USER_CREATED for retry user_id=%s", user_id)
    return published


async def publish_email_verification(
    producer: ResilientKafkaProducer,
    settings: Settings,
    *,
    user_id: UUID,
    email: str,
    token: str,
) -> bool:
    published = await producer.publish(
        topic=settings.kafka_user_events_topic,
        value={
            "event_type": "EMAIL_VERIFICATION_SENT",
            "user_id": str(user_id),
            "email": email,
            "token": token,
        },
        key=str(user_id).encode("utf-8"),
    )
    if published:
        logger.info("Published EMAIL_VERIFICATION_SENT user_id=%s", user_id)
    else:
        logger.warning("Queued EMAIL_VERIFICATION_SENT for retry user_id=%s", user_id)
    return published


async def publish_tutor_verified(
    producer: ResilientKafkaProducer,
    settings: Settings,
    *,
    user_id: UUID,
) -> bool:
    published = await producer.publish(
        topic=settings.kafka_user_events_topic,
        value={
            "event_type": "TUTOR_VERIFIED",
            "user_id": str(user_id),
        },
        key=str(user_id).encode("utf-8"),
    )
    if published:
        logger.info("Published TUTOR_VERIFIED user_id=%s", user_id)
    else:
        logger.warning("Queued TUTOR_VERIFIED for retry user_id=%s", user_id)
    return published

async def publish_tutor_application_submitted(
    producer: ResilientKafkaProducer,
    settings: Settings,
    *,
    user_id: UUID,
    bio: str,
    subjects: list[str],
    hourly_rate: str,
    documents: list[dict],
) -> bool:
    published = await producer.publish(
        topic="VERIFICATION_EVENTS",
        value={
            "event": "TUTOR_APPLICATION_SUBMITTED",
            "userId": str(user_id),
            "bio": bio,
            "subjects": subjects,
            "hourly_rate": hourly_rate,
            "documents": documents,
            "status": "PENDING"
        },
        key=str(user_id).encode("utf-8"),
    )
    if published:
        logger.info("Published TUTOR_APPLICATION_SUBMITTED user_id=%s", user_id)
    else:
        logger.warning("Queued TUTOR_APPLICATION_SUBMITTED for retry user_id=%s", user_id)
    return published
