import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.config import Settings
from app.kafka.producer import ResilientKafkaProducer

logger = logging.getLogger(__name__)


async def publish_session_starting_soon(
    producer: ResilientKafkaProducer,
    *,
    session_id: UUID,
    title: str,
    participant_ids: list[UUID],
    scheduled_time: datetime,
) -> None:
    try:
        await producer.publish(
            topic="SESSION_EVENTS",
            value={
                "event_type": "SESSION_STARTING_SOON",
                "session_id": str(session_id),
                "title": title,
                "participant_ids": [str(p) for p in participant_ids],
                "scheduled_time": scheduled_time.isoformat(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            key=str(session_id).encode(),
        )
        logger.info("Published SESSION_STARTING_SOON session=%s participants=%d", session_id, len(participant_ids))
    except Exception:
        logger.warning("Failed to publish SESSION_STARTING_SOON session=%s", session_id)


async def publish_session_cancelled(
    producer: ResilientKafkaProducer,
    *,
    session_id: UUID,
    title: str,
    participant_ids: list[UUID],
) -> None:
    try:
        await producer.publish(
            topic="SESSION_EVENTS",
            value={
                "event_type": "SESSION_CANCELLED",
                "session_id": str(session_id),
                "title": title,
                "participant_ids": [str(p) for p in participant_ids],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            key=str(session_id).encode(),
        )
        logger.info("Published SESSION_CANCELLED session=%s participants=%d", session_id, len(participant_ids))
    except Exception:
        logger.warning("Failed to publish SESSION_CANCELLED session=%s", session_id)


async def publish_session_enrolled(
    producer: ResilientKafkaProducer,
    *,
    user_email: str,
    user_id: UUID,
    session_id: UUID,
    title: str,
    description: str | None,
    address: str,
    latitude: float,
    longitude: float,
    scheduled_time: datetime,
    session_type: str,
    subject_tags: list[str],
) -> None:
    try:
        await producer.publish(
            topic="SESSION_EVENTS",
            value={
                "event_type": "SESSION_ENROLLED",
                "user_id": str(user_id),
                "email": user_email,
                "session_id": str(session_id),
                "title": title,
                "description": description or "",
                "address": address,
                "latitude": latitude,
                "longitude": longitude,
                "scheduled_time": scheduled_time.isoformat(),
                "session_type": session_type,
                "subject_tags": subject_tags,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            key=str(user_id).encode(),
        )
        logger.info("Published SESSION_ENROLLED user=%s session=%s", user_id, session_id)
    except Exception:
        logger.warning("Failed to publish SESSION_ENROLLED user=%s session=%s", user_id, session_id)


async def publish_session_rated(
    producer: ResilientKafkaProducer,
    settings: Settings,
    *,
    session_id: UUID,
    tutor_id: UUID,
    student_id: UUID,
    rating: int,
    session_average_rating: float,
    session_total_ratings: int,
    created_at: datetime,
) -> None:
    event_id = str(uuid4())
    published = await producer.publish(
        topic=settings.kafka_rating_events_topic,
        value={
            "event": "SESSION_RATED",
            "event_type": "SESSION_RATED",
            "event_id": event_id,
            "sessionId": str(session_id),
            "studentId": str(student_id),
            "tutorId": str(tutor_id),
            "rating": rating,
            "sessionAverageRating": session_average_rating,
            "sessionTotalRatings": session_total_ratings,
            "createdAt": created_at.replace(tzinfo=timezone.utc).isoformat(),
        },
        key=str(session_id).encode("utf-8"),
    )
    if published:
        logger.info(
            "Published SESSION_RATED session_id=%s tutor_id=%s rating=%d",
            session_id,
            tutor_id,
            rating,
        )
    else:
        logger.warning(
            "Queued SESSION_RATED for retry session_id=%s tutor_id=%s",
            session_id,
            tutor_id,
        )
