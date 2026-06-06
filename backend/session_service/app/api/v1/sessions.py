from __future__ import annotations

import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user_id, get_user_email
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models.session import SessionStatus, SessionType
from app.schemas.session import (
    NearbySearchParams,
    SessionCreate,
    SessionRead,
    SessionStatusUpdate,
    SessionUpdate,
)
from app.services.nearby_sessions_cache import NearbySessionsCacheService
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_session_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> SessionService:
    return SessionService(db)


def get_kafka_producer(request: Request):
    return getattr(request.app.state, "kafka_producer", None)


def get_cache(request: Request, settings: Settings = Depends(get_settings)) -> NearbySessionsCacheService:
    redis = getattr(request.app.state, "redis", None)
    return NearbySessionsCacheService(redis, settings)


@router.get("/locations/search")
async def search_locations(
    query: str = Query(..., min_length=2, description="Location search query"),
):
    """Proxy to OpenStreetMap Nominatim for location autocomplete."""
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "StudySync/1.0 (contact: admin@studysync.com)"},
            timeout=8.0,
        ) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 6, "addressdetails": 0},
            )
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=503, detail="Location service timed out.")
    except httpx.HTTPStatusError as exc:
        logger.error("Nominatim error: %s", exc)
        raise HTTPException(status_code=502, detail="Location service error.")
    except Exception as exc:
        logger.error("Location search failed: %s", exc)
        raise HTTPException(status_code=500, detail="Location search unavailable.")

    return [
        {
            "name": item["display_name"],
            "latitude": float(item["lat"]),
            "longitude": float(item["lon"]),
        }
        for item in data
        if item.get("lat") and item.get("lon")
    ]


@router.post("/", response_model=SessionRead, status_code=201)
async def create_session(
    payload: SessionCreate,
    user_id: UUID = Depends(get_current_user_id),
    service: SessionService = Depends(get_session_service),
) -> SessionRead:
    return await service.create_session(host_id=user_id, data=payload)


@router.get("/", response_model=list[SessionRead])
async def list_all_sessions(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: SessionService = Depends(get_session_service),
) -> list[SessionRead]:
    return await service.list_all(limit=limit, offset=offset)


@router.get("/nearby", response_model=list[SessionRead])
async def nearby_sessions(
    longitude: float = Query(..., ge=-180, le=180),
    latitude: float = Query(..., ge=-90, le=90),
    radius_km: float = Query(default=10.0, gt=0, le=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session_type: SessionType | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    subject_tags: list[str] | None = Query(default=None),
    _: UUID = Depends(get_current_user_id),
    service: SessionService = Depends(get_session_service),
    cache: NearbySessionsCacheService = Depends(get_cache),
) -> list[SessionRead]:
    params = NearbySearchParams(
        longitude=longitude,
        latitude=latitude,
        radius_km=radius_km,
        limit=limit,
        offset=offset,
        session_type=session_type,
        min_price=min_price,
        max_price=max_price,
        subject_tags=subject_tags,
    )
    return await service.nearby(params=params, cache=cache)


@router.get("/my", response_model=list[SessionRead])
async def my_sessions(
    user_id: UUID = Depends(get_current_user_id),
    service: SessionService = Depends(get_session_service),
) -> list[SessionRead]:
    return await service.list_by_host(host_id=user_id)


@router.get("/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: UUID,
    _: UUID = Depends(get_current_user_id),
    service: SessionService = Depends(get_session_service),
) -> SessionRead:
    return await service.get_session(session_id)


@router.patch("/{session_id}", response_model=SessionRead)
async def update_session(
    session_id: UUID,
    payload: SessionUpdate,
    user_id: UUID = Depends(get_current_user_id),
    service: SessionService = Depends(get_session_service),
) -> SessionRead:
    return await service.update_session(session_id, requester_id=user_id, data=payload)


@router.patch("/{session_id}/cancel", response_model=SessionRead)
async def cancel_session(
    session_id: UUID,
    request: Request,
    user_id: UUID = Depends(get_current_user_id),
    service: SessionService = Depends(get_session_service),
) -> SessionRead:
    kafka_producer = get_kafka_producer(request)
    return await service.cancel_session(session_id, requester_id=user_id, kafka_producer=kafka_producer)


@router.patch("/{session_id}/status", response_model=SessionRead)
async def update_session_status(
    session_id: UUID,
    payload: SessionStatusUpdate,
    request: Request,
    user_id: UUID = Depends(get_current_user_id),
    service: SessionService = Depends(get_session_service),
) -> SessionRead:
    kafka_producer = getattr(request.app.state, "kafka_producer", None)
    return await service.update_status(
        session_id,
        requester_id=user_id,
        new_status=payload.status,
        kafka_producer=kafka_producer,
    )


@router.post("/{session_id}/join", response_model=SessionRead)
async def join_session(
    session_id: UUID,
    request: Request,
    user_id: UUID = Depends(get_current_user_id),
    service: SessionService = Depends(get_session_service),
) -> SessionRead:
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    user_email = await get_user_email(user_id, token)
    kafka_producer = get_kafka_producer(request)
    return await service.join_free_session(
        session_id=session_id,
        user_id=user_id,
        kafka_producer=kafka_producer,
        user_email=user_email,
    )


@router.post("/{session_id}/leave", response_model=SessionRead)
async def leave_session(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    service: SessionService = Depends(get_session_service),
) -> SessionRead:
    return await service.leave_session(session_id, user_id)


@router.get("/{session_id}/participants", response_model=list[UUID])
async def get_participants(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    service: SessionService = Depends(get_session_service),
) -> list[UUID]:
    return await service.get_participants(session_id, requester_id=user_id)
