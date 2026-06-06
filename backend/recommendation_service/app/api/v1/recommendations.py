from fastapi import APIRouter, Depends, Query, HTTPException
from uuid import UUID
from typing import List
from app.api.deps import get_recommendation_service, get_current_user_id
from pydantic import BaseModel

router = APIRouter()

@router.get("/top")
async def get_top_tutors(
    limit: int = Query(10, ge=1, le=50),
    service = Depends(get_recommendation_service)
):
    return await service.get_top_ranked_tutors(limit)

@router.get("/trending")
async def get_trending_tutors(
    service = Depends(get_recommendation_service)
):
    return await service.get_trending_tutors()

@router.get("/subject/{subject}")
async def get_by_subject(
    subject: str,
    service = Depends(get_recommendation_service)
):
    return await service.get_recommendations_by_subject(subject)

@router.get("/search")
async def search_recommendations(
    subjects: List[str] = Query(None),
    min_rating: float = Query(None, ge=0, le=5),
    is_verified: bool = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service = Depends(get_recommendation_service)
):
    """
    [NEW] Flexible search and filter API for recommendations.
    Pagination and sorting by score are handled by the service.
    """
    return await service.search_tutors(subjects, min_rating, is_verified, page, per_page)

@router.get("/nearby")
async def get_nearby_recommendations(
    lat: float, lon: float, radius: int = 10,
    service = Depends(get_recommendation_service)
):
    return await service.get_nearby_tutors(lat, lon, radius)

@router.get("/user/{user_id}", dependencies=[Depends(get_current_user_id)])
async def get_personalized(
    user_id: UUID, 
    current_user_id: UUID = Depends(get_current_user_id),
    service = Depends(get_recommendation_service)
):
    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to user recommendations")
    return await service.get_personalized_recommendations(user_id)

@router.get("/tutor/{tutor_id}/similar")
async def get_similar_tutors(
    tutor_id: UUID,
    limit: int = Query(5, ge=1, le=20),
    service = Depends(get_recommendation_service)
):
    return await service.get_similar_tutors(tutor_id, limit)

@router.get("/tutor/{tutor_id}")
async def get_tutor_metrics(tutor_id: UUID, service = Depends(get_recommendation_service)):
    metrics = await service.get_tutor_metrics(tutor_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Tutor metrics not found")
    return metrics

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/health/ready")
async def health_ready(service = Depends(get_recommendation_service)):
    """
    [NEW] Deep health check verifying connectivity to Postgres, Redis, and Kafka.
    """
    return await service.get_readiness_status()

# --- ADMIN ENDPOINTS ---

@router.post("/admin/recalculate", status_code=202)
async def trigger_recalculation(
    tutor_id: UUID = None,
    service = Depends(get_recommendation_service)
    # Admin auth dependency should be added here
):
    """
    [NEW] Admin-only API to manually trigger score recalculation.
    If tutor_id is None, it triggers a global refresh.
    """
    await service.trigger_recalculation(tutor_id)
    return {"message": "Recalculation task initiated"}

@router.post("/admin/cache/refresh")
async def refresh_cache(
    target: str = Query(..., regex="^(top|trending|all)$"),
    service = Depends(get_recommendation_service)
):
    """
    [NEW] Admin-only API to clear specific or all recommendation caches.
    Useful after bulk data imports or major scoring logic updates.
    """
    count = await service.refresh_cache(target)
    return {"message": f"Successfully cleared {count} cache keys"}