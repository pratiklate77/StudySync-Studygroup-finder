from __future__ import annotations

import logging
from uuid import UUID

from app.core.config import Settings
from app.kafka.producer import ResilientKafkaProducer

logger = logging.getLogger(__name__)


# --- Payload builders ---

def group_created_payload(group_id: UUID, owner_id: UUID, name: str) -> dict:
    return {
        "event_type": "GROUP_CREATED",
        "group_id": str(group_id),
        "owner_id": str(owner_id),
        "name": name,
    }


def user_joined_payload(group_id: UUID, user_id: UUID, role: str) -> dict:
    return {
        "event_type": "USER_JOINED_GROUP",
        "group_id": str(group_id),
        "user_id": str(user_id),
        "role": role,
    }


def user_left_payload(group_id: UUID, user_id: UUID) -> dict:
    return {
        "event_type": "USER_LEFT_GROUP",
        "group_id": str(group_id),
        "user_id": str(user_id),
    }


def group_deleted_payload(group_id: UUID, owner_id: UUID) -> dict:
    return {
        "event_type": "GROUP_DELETED",
        "group_id": str(group_id),
        "owner_id": str(owner_id),
    }


def join_request_accepted_payload(group_id: UUID, group_name: str, user_id: UUID) -> dict:
    return {
        "event_type": "JOIN_REQUEST_ACCEPTED",
        "group_id": str(group_id),
        "group_name": group_name,
        "user_id": str(user_id),
    }


def join_request_rejected_payload(group_id: UUID, group_name: str, user_id: UUID) -> dict:
    return {
        "event_type": "JOIN_REQUEST_REJECTED",
        "group_id": str(group_id),
        "group_name": group_name,
        "user_id": str(user_id),
    }


def group_invitation_payload(group_id: UUID, group_name: str, invited_user_id: UUID, inviter_id: UUID) -> dict:
    return {
        "event_type": "GROUP_INVITATION",
        "group_id": str(group_id),
        "group_name": group_name,
        "invited_user_id": str(invited_user_id),
        "inviter_id": str(inviter_id),
    }


# --- Publisher ---

async def publish_event(
    producer: ResilientKafkaProducer,
    settings: Settings,
    payload: dict,
    key: str,
) -> None:
    published = await producer.publish(
        topic=settings.kafka_group_events_topic,
        value=payload,
        key=key.encode("utf-8"),
    )
    if published:
        logger.info("Published %s key=%s", payload.get("event_type"), key)
    else:
        logger.warning("Queued %s for retry key=%s", payload.get("event_type"), key)
