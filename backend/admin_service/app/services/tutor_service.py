from __future__ import annotations

import logging
import uuid

from app.kafka.producer import AdminKafkaProducer
from app.repositories.audit_repo import AuditRepository
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserSummary

logger = logging.getLogger(__name__)


class TutorService:
    """Service for tutor-related operations."""

    def __init__(
        self,
        user_repo: UserRepository,
        audit_repo: AuditRepository,
        kafka_producer: AdminKafkaProducer,
    ):
        self.user_repo = user_repo
        self.audit_repo = audit_repo
        self.kafka_producer = kafka_producer

    async def verify_platform_tutor(self, user_id: uuid.UUID, admin_id: uuid.UUID) -> bool:
        """Mark a tutor verified in Identity DB and publish TUTOR_VERIFIED event."""
        success = await self.user_repo.verify_tutor(user_id)
        if not success:
            return False

        await self.kafka_producer.publish_tutor_verified(user_id=str(user_id))

        await self.audit_repo.log_action(
            admin_id=admin_id,
            action="TUTOR_VERIFIED",
            target_type="user",
            target_id=str(user_id),
        )
        return True