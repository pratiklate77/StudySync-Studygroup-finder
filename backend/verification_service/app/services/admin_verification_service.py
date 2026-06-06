from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.database import db_manager
from app.events.kafka_producer import VerificationKafkaProducer
from app.models.tutor_verification_request import TutorVerificationRequest
from app.models.enums import VerificationStatus
from app.models.verification_document import VerificationDocument
from app.schemas.verification import (
    AdminVerificationListItem,
    AdminVerificationListResponse,
    AdminVerificationDetail,
    DocumentResponse,
)

logger = logging.getLogger(__name__)


class AdminVerificationService:
    """Business logic for admin verification operations on TutorVerificationRequest."""

    def __init__(self, redis: Redis, kafka_producer: VerificationKafkaProducer, settings: Settings):
        self.redis = redis
        self.kafka_producer = kafka_producer
        self.settings = settings

    async def list_requests(
        self,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
    ) -> AdminVerificationListResponse:
        """List tutor verification requests with optional status filter. Uses SQL pagination."""
        async with db_manager.SessionLocal() as session:
            base_query = select(TutorVerificationRequest)
            count_query = select(func.count()).select_from(TutorVerificationRequest)

            if status:
                base_query = base_query.where(TutorVerificationRequest.status == status)
                count_query = count_query.where(TutorVerificationRequest.status == status)

            total_result = await session.execute(count_query)
            total = total_result.scalar() or 0

            offset = (page - 1) * per_page
            result = await session.execute(
                base_query
                .order_by(TutorVerificationRequest.created_at.asc())
                .offset(offset)
                .limit(per_page)
            )
            requests = result.scalars().all()

            # Get document counts in one query
            request_ids = [r.id for r in requests]
            doc_counts: dict[uuid.UUID, int] = {}
            if request_ids:
                doc_result = await session.execute(
                    select(VerificationDocument.request_id, func.count().label("cnt"))
                    .where(VerificationDocument.request_id.in_(request_ids))
                    .group_by(VerificationDocument.request_id)
                )
                for row in doc_result:
                    doc_counts[row.request_id] = row.cnt

        items = [
            AdminVerificationListItem(
                id=r.id,
                user_id=r.user_id,
                request_type="tutor_application",
                status=r.status.value if hasattr(r.status, 'value') else r.status,
                submitted_at=r.created_at,
                document_count=doc_counts.get(r.id, 0),
            )
            for r in requests
        ]

        return AdminVerificationListResponse(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        )

    async def get_verification_detail(self, request_id: uuid.UUID) -> Optional[AdminVerificationDetail]:
        """Get detailed tutor verification request for admin with documents eagerly loaded."""
        async with db_manager.SessionLocal() as session:
            result = await session.execute(
                select(TutorVerificationRequest)
                .options(selectinload(TutorVerificationRequest.documents))
                .where(TutorVerificationRequest.id == request_id)
            )
            request = result.scalars().first()

        if not request:
            return None

        return AdminVerificationDetail(
            id=request.id,
            user_id=request.user_id,
            request_type="tutor_application",
            status=request.status.value if hasattr(request.status, 'value') else request.status,
            documents=[
                DocumentResponse(
                    id=doc.id,
                    verification_request_id=doc.request_id,
                    file_name=doc.file_name,
                    file_url=doc.file_url,
                    document_type=doc.document_type,
                    uploaded_at=doc.uploaded_at,
                )
                for doc in (request.documents or [])
            ],
            submitted_at=request.created_at,
            admin_notes=request.rejection_reason,
            reviewed_by=request.reviewed_by,
            reviewed_at=request.reviewed_at,
        )

    async def mark_under_review(
        self,
        request_id: uuid.UUID,
        admin_id: uuid.UUID,
        admin_notes: Optional[str] = None,
    ) -> bool:
        """Mark a pending request as under_review."""
        async with db_manager.SessionLocal() as session:
            result = await session.execute(
                select(TutorVerificationRequest).where(TutorVerificationRequest.id == request_id)
            )
            request = result.scalars().first()
            if not request or request.status != VerificationStatus.PENDING:
                return False

            request.status = VerificationStatus.UNDER_REVIEW
            request.reviewed_by = admin_id
            await session.commit()

        logger.info("Marked tutor verification request %s as under_review by admin %s", request_id, admin_id)
        await self.redis.delete(f"verification:status:{request.user_id}")
        return True

    async def approve_request(
        self,
        request_id: uuid.UUID,
        admin_id: uuid.UUID,
        admin_notes: Optional[str] = None,
    ) -> bool:
        """Approve a tutor verification request and publish TUTOR_VERIFIED event."""
        async with db_manager.SessionLocal() as session:
            result = await session.execute(
                select(TutorVerificationRequest).where(TutorVerificationRequest.id == request_id)
            )
            request = result.scalars().first()
            if not request or request.status not in {VerificationStatus.PENDING, VerificationStatus.UNDER_REVIEW}:
                return False

            request.status = VerificationStatus.VERIFIED
            request.reviewed_by = admin_id
            request.reviewed_at = datetime.utcnow()
            await session.commit()

        logger.info("Approved tutor verification request %s by admin %s", request_id, admin_id)

        # Publish TUTOR_VERIFIED to USER_EVENTS so identity_service, session_service, recommendation_service can react
        await self.kafka_producer.publish_tutor_verified(
            request_id=str(request_id),
            user_id=str(request.user_id),
        )
        await self.redis.delete(f"verification:status:{request.user_id}")
        return True

    async def reject_request(
        self,
        request_id: uuid.UUID,
        admin_id: uuid.UUID,
        reason: str,
    ) -> bool:
        """Reject a tutor verification request and publish TUTOR_REJECTED event."""
        async with db_manager.SessionLocal() as session:
            result = await session.execute(
                select(TutorVerificationRequest).where(TutorVerificationRequest.id == request_id)
            )
            request = result.scalars().first()
            if not request or request.status not in {VerificationStatus.PENDING, VerificationStatus.UNDER_REVIEW}:
                return False

            request.status = VerificationStatus.REJECTED
            request.reviewed_by = admin_id
            request.reviewed_at = datetime.utcnow()
            request.rejection_reason = reason
            await session.commit()

        logger.info("Rejected tutor verification request %s by admin %s", request_id, admin_id)

        # Publish TUTOR_REJECTED to USER_EVENTS so notification_service can notify
        await self.kafka_producer.publish_tutor_rejected(
            request_id=str(request_id),
            user_id=str(request.user_id),
            reason=reason,
        )
        await self.redis.delete(f"verification:status:{request.user_id}")
        return True