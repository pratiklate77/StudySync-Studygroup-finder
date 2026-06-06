from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.database import db_manager
from app.events.kafka_producer import VerificationKafkaProducer
from app.models.verification_request import VerificationRequest
from app.models.document import Document
from app.schemas.verification import (
    DocumentResponse,
    VerificationRequestResponse,
    VerificationStatusResponse,
    VerificationHistoryResponse,
)

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = {"pending", "under_review"}


class VerificationService:
    """Business logic for verification operations."""

    def __init__(self, redis: Redis, kafka_producer: VerificationKafkaProducer, settings: Settings):
        self.redis = redis
        self.kafka_producer = kafka_producer
        self.settings = settings

    async def submit_verification_request(
        self,
        user_id: uuid.UUID,
        request_type: str,
    ) -> VerificationRequestResponse:
        """Submit a new verification request. Rejects if an active one already exists."""
        async with db_manager.SessionLocal() as session:
            # Resubmission guard — block if pending or under_review already exists
            existing = await session.execute(
                select(VerificationRequest).where(
                    and_(
                        VerificationRequest.user_id == user_id,
                        VerificationRequest.request_type == request_type,
                        VerificationRequest.status.in_(list(_ACTIVE_STATUSES)),
                    )
                )
            )
            if existing.scalars().first():
                raise ValueError(f"An active {request_type} verification request already exists")

            request_id = uuid.uuid4()
            verification_request = VerificationRequest(
                id=request_id,
                user_id=user_id,
                request_type=request_type,
                status="pending",
            )
            session.add(verification_request)
            await session.commit()
            await session.refresh(verification_request)
            logger.info("Created verification request %s for user %s", request_id, user_id)

        await self.kafka_producer.publish_verification_submitted(
            request_id=str(request_id),
            user_id=str(user_id),
            request_type=request_type,
            document_count=0,
        )
        await self.redis.delete(f"verification:status:{user_id}")

        return VerificationRequestResponse(
            id=request_id,
            user_id=user_id,
            request_type=request_type,
            status="pending",
            submitted_at=verification_request.submitted_at,
            documents=[],
        )

    async def get_verification_status(self, user_id: uuid.UUID) -> Optional[VerificationStatusResponse]:
        """Get latest verification status for a user, with Redis cache."""
        cache_key = f"verification:status:{user_id}"
        cached = await self.redis.get(cache_key);
        if cached:
            return VerificationStatusResponse(**json.loads(cached))

        async with db_manager.SessionLocal() as session:
            result = await session.execute(
                select(VerificationRequest)
                .where(VerificationRequest.user_id == user_id)
                .order_by(VerificationRequest.submitted_at.desc())
            )
            request = result.scalars().first()
            if not request:
                return None

            doc_count_result = await session.execute(
                select(func.count()).where(Document.verification_request_id == request.id)
            )
            doc_count = doc_count_result.scalar() or 0

        response = VerificationStatusResponse(
            user_id=request.user_id,
            request_id=request.id,
            request_type=request.request_type,
            status=request.status,
            submitted_at=request.submitted_at,
            reviewed_at=request.reviewed_at,
            admin_notes=request.admin_notes,
            document_count=doc_count,
        )
        await self.redis.setex(
            cache_key,
            self.settings.redis_cache_ttl_seconds,
            json.dumps(response.model_dump(mode="json")),
        )
        return response

    async def get_verification_history(self, user_id: uuid.UUID) -> VerificationHistoryResponse:
        """Get all verification requests for a user across all time."""
        async with db_manager.SessionLocal() as session:
            result = await session.execute(
                select(VerificationRequest)
                .options(selectinload(VerificationRequest.documents))
                .where(VerificationRequest.user_id == user_id)
                .order_by(VerificationRequest.submitted_at.desc())
            )
            requests = result.scalars().all()

        items = [self._to_response(r) for r in requests]
        return VerificationHistoryResponse(user_id=user_id, total=len(items), requests=items)

    async def upload_document(
        self,
        user_id: uuid.UUID,
        request_type: str,
        file_name: str,
        file_url: str,
        document_type: str,
    ) -> Optional[DocumentResponse]:
        """Upload a document to an existing active verification request."""
        async with db_manager.SessionLocal() as session:
            req_result = await session.execute(
                select(VerificationRequest).where(
                    and_(
                        VerificationRequest.user_id == user_id,
                        VerificationRequest.request_type == request_type,
                        VerificationRequest.status.in_(list(_ACTIVE_STATUSES)),
                    )
                ).order_by(VerificationRequest.submitted_at.desc())
            )
            request = req_result.scalars().first()
            if not request:
                return None

            doc_count_result = await session.execute(
                select(func.count()).where(Document.verification_request_id == request.id)
            )
            doc_count = doc_count_result.scalar() or 0
            if doc_count >= self.settings.max_documents_per_request:
                raise ValueError(f"Maximum {self.settings.max_documents_per_request} documents allowed per request")

            document = Document(
                id=uuid.uuid4(),
                verification_request_id=request.id,
                file_name=file_name,
                file_url=file_url,
                document_type=document_type,
            )
            session.add(document)
            await session.commit()
            await session.refresh(document)

        await self.redis.delete(f"verification:status:{user_id}")
        logger.info("Uploaded document %s for request %s", document.id, request.id)

        return DocumentResponse(
            id=document.id,
            verification_request_id=document.verification_request_id,
            file_name=document.file_name,
            file_url=document.file_url,
            document_type=document.document_type,
            uploaded_at=document.uploaded_at,
        )

    async def get_user_documents(self, user_id: uuid.UUID) -> list[DocumentResponse]:
        """Get all documents for the user's latest verification request."""
        async with db_manager.SessionLocal() as session:
            req_result = await session.execute(
                select(VerificationRequest)
                .options(selectinload(VerificationRequest.documents))
                .where(VerificationRequest.user_id == user_id)
                .order_by(VerificationRequest.submitted_at.desc())
            )
            request = req_result.scalars().first()
            if not request:
                return []

            return [
                DocumentResponse(
                    id=doc.id,
                    verification_request_id=doc.verification_request_id,
                    file_name=doc.file_name,
                    file_url=doc.file_url,
                    document_type=doc.document_type,
                    uploaded_at=doc.uploaded_at,
                )
                for doc in request.documents
            ]

    @staticmethod
    def _to_response(request: VerificationRequest) -> VerificationRequestResponse:
        """Convert model to response — documents must already be loaded via selectinload."""
        docs = [
            DocumentResponse(
                id=doc.id,
                verification_request_id=doc.verification_request_id,
                file_name=doc.file_name,
                file_url=doc.file_url,
                document_type=doc.document_type,
                uploaded_at=doc.uploaded_at,
            )
            for doc in (request.documents or [])
        ]
        return VerificationRequestResponse(
            id=request.id,
            user_id=request.user_id,
            request_type=request.request_type,
            status=request.status,
            admin_notes=request.admin_notes,
            reviewed_by=request.reviewed_by,
            submitted_at=request.submitted_at,
            reviewed_at=request.reviewed_at,
            documents=docs,
        )
