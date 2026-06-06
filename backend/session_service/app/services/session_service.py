from datetime import UTC, datetime, timezone
from uuid import UUID
import json

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.events.kafka_producer import publish_session_enrolled, publish_session_cancelled
from app.models.session import GeoPoint, Session, SessionStatus, SessionType
from app.repositories.session_repository import SessionRepository
from app.repositories.verified_tutor_repository import VerifiedTutorRepository
from app.schemas.session import NearbySearchParams, SessionCreate, SessionRead, SessionUpdate
from app.services.nearby_sessions_cache import NearbySessionsCacheService
from app.utils.mappers import session_to_read


class SessionService:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._sessions = SessionRepository(db)
        self._verified_tutors = VerifiedTutorRepository(db)

    async def create_session(self, host_id: UUID, data: SessionCreate) -> SessionRead:
        is_verified = await self._verified_tutors.is_verified(host_id)
        # Paid sessions require full verification; free sessions are open to all tutors
        if data.session_type == SessionType.paid and not is_verified:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Only verified tutors can create paid sessions",
            )
        if not is_verified and not await self._verified_tutors.has_tutor_record(host_id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Only tutors can create sessions",
            )
        if data.scheduled_time.replace(tzinfo=None) <= datetime.utcnow():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="scheduled_time must be in the future",
            )
        if data.session_type == SessionType.free and data.price > 0:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Free sessions cannot have a price",
            )
        session = Session(
            host_id=host_id,
            title=data.title,
            description=data.description,
            session_type=data.session_type,
            price=data.price,
            max_participants=data.max_participants,
            scheduled_time=data.scheduled_time,
            location=GeoPoint(coordinates=[data.location.longitude, data.location.latitude]),
            address=data.address or "",
            subject_tags=data.subject_tags,
        )
        return session_to_read(await self._sessions.create(session))

    async def get_session(self, session_id: UUID) -> SessionRead:
        return session_to_read(await self._get_or_404(session_id))
    
    
    async def update_session(
        self, session_id: UUID, requester_id: UUID, data: SessionUpdate
    ) -> SessionRead:
        session = await self._get_or_404(session_id)
        if session.host_id != requester_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only the host can update this session")
        if session.status not in (SessionStatus.scheduled,):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Only scheduled sessions can be updated",
            )
        fields = data.model_dump(exclude_none=True)
        if not fields:
            return session_to_read(session)
        updated = await self._sessions.update(session_id, fields)
        return session_to_read(updated)  # type: ignore[arg-type]

    async def cancel_session(self, session_id: UUID, requester_id: UUID, kafka_producer=None) -> SessionRead:
        session = await self._get_or_404(session_id)
        if session.host_id != requester_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only the host can cancel this session")
        if session.status == SessionStatus.cancelled:
            return session_to_read(session)
        if session.status not in (SessionStatus.scheduled, SessionStatus.active):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Completed sessions cannot be cancelled",
            )
        updated = await self._sessions.set_status(session_id, SessionStatus.cancelled)
        if kafka_producer and updated and updated.participants:
            await publish_session_cancelled(
                kafka_producer,
                session_id=session_id,
                title=updated.title,
                participant_ids=list(updated.participants),
            )
        return session_to_read(updated)  # type: ignore[arg-type]

    async def update_status(
        self, session_id: UUID, requester_id: UUID, new_status: SessionStatus,
        kafka_producer=None,
    ) -> SessionRead:
        session = await self._get_or_404(session_id)
        if session.host_id != requester_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only the host can change session status")
        if not SessionRepository.is_valid_transition(session.status, new_status):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Cannot transition from '{session.status}' to '{new_status}'",
            )
        updated = await self._sessions.set_status(session_id, new_status)
        result = session_to_read(updated)  # type: ignore[arg-type]

        # Emit Kafka event to notify all participants
        if kafka_producer and updated:
            event_type = "SESSION_STARTED" if new_status == SessionStatus.active else "SESSION_STATUS_CHANGED"
            participants = list(updated.participants)
            for participant_id in participants:
                event = {
                    "event_type": event_type,
                    "user_id": str(participant_id),
                    "session_id": str(session_id),
                    "session_title": updated.title,
                    "new_status": str(new_status.value),
                    "host_id": str(requester_id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                try:
                    await kafka_producer.publish(
                        topic="SESSION_EVENTS",
                        value=event,
                        key=str(participant_id).encode(),
                    )
                except Exception:
                    pass  # non-critical
        return result

    async def join_free_session(self, session_id: UUID, user_id: UUID, kafka_producer=None, user_email: str | None = None) -> SessionRead:
        session = await self._get_or_404(session_id)
        if session.session_type != SessionType.free:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Use the payment flow to join paid sessions",
            )
        if session.status != SessionStatus.scheduled:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Session is not open for joining")
        if user_id in session.participants:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Already joined this session")
        if not await self._sessions.add_participant(session_id, user_id):
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Session is full")
        result = session_to_read(await self._get_or_404(session_id))
        if kafka_producer and user_email:
            await publish_session_enrolled(
                kafka_producer,
                user_email=user_email,
                user_id=user_id,
                session_id=session_id,
                title=result.title,
                description=result.description,
                address=result.address,
                latitude=result.latitude,
                longitude=result.longitude,
                scheduled_time=result.scheduled_time,
                session_type=result.session_type.value,
                subject_tags=result.subject_tags,
            )
        return result

    async def leave_session(self, session_id: UUID, user_id: UUID) -> SessionRead:
        session = await self._get_or_404(session_id)
        if session.status in (SessionStatus.completed, SessionStatus.cancelled):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Cannot leave a completed or cancelled session",
            )
        if user_id not in session.participants:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="You are not a participant")
        await self._sessions.remove_participant(session_id, user_id)
        return session_to_read(await self._get_or_404(session_id))

    async def get_participants(self, session_id: UUID, requester_id: UUID) -> list[UUID]:
        session = await self._get_or_404(session_id)
        # Allow host and enrolled participants to view roster
        is_host = session.host_id == requester_id
        is_participant = requester_id in session.participants
        if not is_host and not is_participant:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Only the host or enrolled participants can view the participant list",
            )
        participants = await self._sessions.get_participants(session_id)
        return participants or []

    async def add_paid_participant(self, session_id: UUID, student_id: UUID) -> bool:
        session = await self._sessions.get_by_id(session_id)
        if session is None or session.session_type != SessionType.paid:
            return False
        return await self._sessions.add_participant(session_id, student_id)

    async def nearby(
        self,
        params: NearbySearchParams,
        cache: NearbySessionsCacheService,
    ) -> list[SessionRead]:
        # Only cache the default (no filters, no offset) query
        use_cache = (
            params.session_type is None
            and params.min_price is None
            and params.max_price is None
            and params.subject_tags is None
            and params.offset == 0
        )
        if use_cache:
            cached = await cache.get(params.longitude, params.latitude, params.radius_km)
            if cached:
                raw = cache.deserialize(cached)
                return [SessionRead.model_validate(r) for r in raw]

        sessions = await self._sessions.find_nearby(
            longitude=params.longitude,
            latitude=params.latitude,
            radius_meters=params.radius_km * 1000,
            limit=params.limit,
            offset=params.offset,
            session_type=params.session_type,
            min_price=params.min_price,
            max_price=params.max_price,
            subject_tags=params.subject_tags,
        )
        result = [session_to_read(s) for s in sessions]

        if use_cache:
            await cache.set(
                params.longitude,
                params.latitude,
                params.radius_km,
                cache.serialize([r.model_dump(mode="json") for r in result]),
            )
        return result

    async def list_by_host(self, host_id: UUID) -> list[SessionRead]:
        return [session_to_read(s) for s in await self._sessions.list_by_host(host_id)]

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[SessionRead]:
        sessions = await self._sessions.list_all(limit=limit, offset=offset)
        return [session_to_read(s) for s in sessions]

    async def _get_or_404(self, session_id: UUID) -> Session:
        session = await self._sessions.get_by_id(session_id)
        if session is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Session not found")
        return session
