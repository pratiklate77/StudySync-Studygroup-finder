import json
import logging
from datetime import datetime
from typing import Any

from app.core.config import Settings

logger = logging.getLogger("verification-service")


class VerificationKafkaProducer:
    """Publishes verification events to Kafka."""
    
    def __init__(self, aiokafka_producer: Any):
        self.producer = aiokafka_producer
    
    async def publish_tutor_application_submitted(
        self,
        request_id: str,
        user_id: str,
    ) -> bool:
        """Publish tutor application submitted event."""
        if not self.producer:
            logger.warning("Kafka producer not available, skipping TUTOR_APPLICATION_SUBMITTED")
            return False
        try:
            event = {
                "event": "TUTOR_APPLICATION_SUBMITTED",
                "userId": user_id,
                "verificationRequestId": request_id,
                "status": "PENDING",
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.producer.send_and_wait(
                "VERIFICATION_EVENTS",
                json.dumps(event).encode(),
                key=user_id.encode(),
            )
            logger.info(f"Published TUTOR_APPLICATION_SUBMITTED event for request {request_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish TUTOR_APPLICATION_SUBMITTED: {e}")
            return False
            
    async def publish_verification_submitted(
        self,
        request_id: str,
        user_id: str,
        request_type: str,
        document_count: int,
    ) -> bool:
        """Publish verification submitted event."""
        if not self.producer:
            logger.warning("Kafka producer not available, skipping VERIFICATION_SUBMITTED")
            return False
        try:
            event = {
                "event_type": "VERIFICATION_SUBMITTED",
                "request_id": request_id,
                "user_id": user_id,
                "request_type": request_type,
                "document_count": document_count,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.producer.send_and_wait(
                "VERIFICATION_EVENTS",
                json.dumps(event).encode(),
                key=user_id.encode(),
            )
            logger.info(f"Published VERIFICATION_SUBMITTED event for request {request_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish VERIFICATION_SUBMITTED: {e}")
            return False
    
    async def publish_verification_approved(
        self,
        request_id: str,
        user_id: str,
        request_type: str,
        admin_id: str,
        admin_notes: str | None = None,
    ) -> bool:
        """Publish verification approved event."""
        if not self.producer:
            logger.warning("Kafka producer not available, skipping VERIFICATION_APPROVED")
            return False
        try:
            event = {
                "event_type": "VERIFICATION_APPROVED",
                "request_id": request_id,
                "user_id": user_id,
                "request_type": request_type,
                "admin_id": admin_id,
                "admin_notes": admin_notes,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.producer.send_and_wait(
                "VERIFICATION_EVENTS",
                json.dumps(event).encode(),
                key=user_id.encode(),
            )
            logger.info(f"Published VERIFICATION_APPROVED event for request {request_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish VERIFICATION_APPROVED: {e}")
            return False
    
    async def publish_tutor_verified(
        self,
        request_id: str,
        user_id: str,
    ) -> bool:
        """Publish TUTOR_VERIFIED event to USER_EVENTS topic."""
        if not self.producer:
            logger.warning("Kafka producer not available, skipping TUTOR_VERIFIED")
            return False
        try:
            event = {
                "event": "TUTOR_VERIFIED",
                "event_type": "TUTOR_VERIFIED",
                "userId": user_id,
                "user_id": user_id,
                "verificationRequestId": request_id,
                "status": "VERIFIED",
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.producer.send_and_wait(
                "USER_EVENTS",
                json.dumps(event).encode(),
                key=user_id.encode(),
            )
            logger.info(f"Published TUTOR_VERIFIED event for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish TUTOR_VERIFIED: {e}")
            return False

    async def publish_tutor_rejected(
        self,
        request_id: str,
        user_id: str,
        reason: str,
    ) -> bool:
        """Publish TUTOR_REJECTED event to USER_EVENTS topic."""
        if not self.producer:
            logger.warning("Kafka producer not available, skipping TUTOR_REJECTED")
            return False
        try:
            event = {
                "event": "TUTOR_REJECTED",
                "event_type": "TUTOR_REJECTED",
                "userId": user_id,
                "user_id": user_id,
                "verificationRequestId": request_id,
                "reason": reason,
                "status": "REJECTED",
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.producer.send_and_wait(
                "USER_EVENTS",
                json.dumps(event).encode(),
                key=user_id.encode(),
            )
            logger.info(f"Published TUTOR_REJECTED event for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish TUTOR_REJECTED: {e}")
            return False

    async def publish_tutor_suspended(
        self,
        user_id: str,
        reason: str,
    ) -> bool:
        """Publish TUTOR_SUSPENDED event to USER_EVENTS topic."""
        if not self.producer:
            logger.warning("Kafka producer not available, skipping TUTOR_SUSPENDED")
            return False
        try:
            event = {
                "event": "TUTOR_SUSPENDED",
                "event_type": "TUTOR_SUSPENDED",
                "userId": user_id,
                "user_id": user_id,
                "reason": reason,
                "status": "SUSPENDED",
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.producer.send_and_wait(
                "USER_EVENTS",
                json.dumps(event).encode(),
                key=user_id.encode(),
            )
            logger.info(f"Published TUTOR_SUSPENDED event for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish TUTOR_SUSPENDED: {e}")
            return False

    async def publish_verification_rejected(
        self,
        request_id: str,
        user_id: str,
        request_type: str,
        admin_id: str,
        reason: str,
    ) -> bool:
        """Publish verification rejected event."""
        if not self.producer:
            logger.warning("Kafka producer not available, skipping VERIFICATION_REJECTED")
            return False
        try:
            event = {
                "event_type": "VERIFICATION_REJECTED",
                "request_id": request_id,
                "user_id": user_id,
                "request_type": request_type,
                "admin_id": admin_id,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.producer.send_and_wait(
                "VERIFICATION_EVENTS",
                json.dumps(event).encode(),
                key=user_id.encode(),
            )
            logger.info(f"Published VERIFICATION_REJECTED event for request {request_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish VERIFICATION_REJECTED: {e}")
            return False
