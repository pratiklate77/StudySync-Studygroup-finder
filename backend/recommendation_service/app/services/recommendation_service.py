import json
import logging
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, desc, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from app.core.config import Settings
from app.models.tutor_metric import TutorMetric, RecommendationScore, TrendingTutor

logger = logging.getLogger(__name__)

class RecommendationService:
    def __init__(self, db: AsyncSession, redis: Redis, settings: Settings):
        self.db = db
        self.redis = redis
        self.settings = settings
        self.cache_key_prefix = "rec:"

    async def get_top_ranked_tutors(self, limit: int):
        cache_key = f"{self.cache_key_prefix}top:{limit}"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        stmt = select(TutorMetric).order_by(desc(TutorMetric.recommendation_score)).limit(limit)
        result = await self.db.execute(stmt)
        tutors = result.scalars().all()
        
        response_data = [
            {"tutor_id": str(t.tutor_id), "score": t.recommendation_score, "subjects": t.subjects}
            for t in tutors
        ]
        
        await self.redis.setex(cache_key, self.settings.recommendation_cache_ttl, json.dumps(response_data))
        return response_data

    async def get_trending_tutors(self):
        cache_key = f"{self.cache_key_prefix}trending"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
            
        stmt = select(TrendingTutor).order_by(desc(TrendingTutor.trend_score)).limit(10)
        result = await self.db.execute(stmt)
        trending = result.scalars().all()
        
        data = [{"tutor_id": str(t.tutor_id), "trend_score": t.trend_score} for t in trending]
        await self.redis.setex(cache_key, 3600, json.dumps(data))
        return data

    async def get_recommendations_by_subject(self, subject: str):
        cache_key = f"{self.cache_key_prefix}subject:{subject}"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        stmt = select(TutorMetric).where(TutorMetric.subjects.contains([subject])).order_by(desc(TutorMetric.recommendation_score)).limit(10)
        result = await self.db.execute(stmt)
        tutors = result.scalars().all()
        
        data = [{"tutor_id": str(t.tutor_id), "score": t.recommendation_score} for t in tutors]
        await self.redis.setex(cache_key, self.settings.recommendation_cache_ttl, json.dumps(data))
        return data

    async def calculate_score(self, tutor_metric: TutorMetric) -> float:
        """
        Formula: Score = (0.7 * avg_rating) + (0.3 * activity_score)
        """
        rating_component = (tutor_metric.average_rating / 5.0) * 0.7
        activity_component = tutor_metric.activity_score * 0.3
        return min(1.0, rating_component + activity_component)

    async def apply_session_rating_event(
        self,
        *,
        tutor_id: str,
        score: int,
        event_id: str | None = None,
        session_id: str | None = None,
        student_id: str | None = None,
    ) -> bool:
        if score < 1 or score > 5:
            return False

        existing = await self.db.get(TutorMetric, UUID(tutor_id))
        if existing is None:
            metric = TutorMetric(
                tutor_id=UUID(tutor_id),
                average_rating=float(score),
                total_reviews=1,
                sessions_completed=1,
                recommendation_score=await self.calculate_score(
                    TutorMetric(
                        tutor_id=UUID(tutor_id),
                        average_rating=float(score),
                        total_reviews=1,
                        sessions_completed=1,
                    )
                ),
                last_activity=datetime.now(timezone.utc),
            )
            self.db.add(metric)
            await self.db.commit()
            return True

        total_reviews = existing.total_reviews + 1
        new_average = ((existing.average_rating * existing.total_reviews) + score) / total_reviews
        existing.average_rating = new_average
        existing.total_reviews = total_reviews
        existing.sessions_completed = existing.sessions_completed + 1
        existing.last_activity = datetime.now(timezone.utc)
        existing.recommendation_score = await self.calculate_score(existing)

        await self.db.commit()
        return True

    async def search_tutors(
        self, subjects: list[str] | None, min_rating: float | None, is_verified: bool | None, page: int, per_page: int
    ):
        stmt = select(TutorMetric)
        filters = []
        if subjects:
            filters.append(TutorMetric.subjects.contains(subjects))
        if min_rating:
            filters.append(TutorMetric.average_rating >= min_rating)
        if is_verified is not None:
            filters.append(TutorMetric.is_verified == is_verified)
        
        if filters:
            stmt = stmt.where(and_(*filters))
            
        stmt = stmt.order_by(desc(TutorMetric.recommendation_score)).offset((page - 1) * per_page).limit(per_page)
        result = await self.db.execute(stmt)
        tutors = result.scalars().all()
        return [{"tutor_id": str(t.tutor_id), "score": t.recommendation_score, "rating": t.average_rating} for t in tutors]

    async def get_nearby_tutors(self, lat: float, lon: float, radius_km: int):
        """
        Uses the Haversine formula implemented in SQL for simple distance filtering
        without requiring heavy PostGIS extensions.
        """
        distance_query = 6371 * func.acos(
            func.cos(func.radians(lat))
            * func.cos(func.radians(TutorMetric.latitude))
            * func.cos(func.radians(TutorMetric.longitude) - func.radians(lon))
            + func.sin(func.radians(lat)) * func.sin(func.radians(TutorMetric.latitude))
        )
        
        stmt = select(TutorMetric).where(
            and_(
                TutorMetric.latitude.isnot(None),
                TutorMetric.longitude.isnot(None),
                distance_query <= radius_km
            )
        ).order_by(distance_query)
        
        result = await self.db.execute(stmt)
        tutors = result.scalars().all()
        return [{"tutor_id": str(t.tutor_id), "subjects": t.subjects} for t in tutors]

    async def get_personalized_recommendations(self, user_id: UUID):
        # In a real system, we'd fetch user preferences from Identity Service or Session history.
        # For now, we utilize the global top tutors as a fallback with high weighting.
        return await self.get_top_ranked_tutors(10)

    async def get_similar_tutors(self, tutor_id: UUID, limit: int):
        base_tutor = await self.db.get(TutorMetric, tutor_id)
        if not base_tutor:
            return []

        stmt = select(TutorMetric).where(
            and_(
                TutorMetric.tutor_id != tutor_id,
                or_(
                    TutorMetric.subjects.contains(base_tutor.subjects),
                    TutorMetric.average_rating >= (base_tutor.average_rating - 0.5)
                )
            )
        ).order_by(desc(TutorMetric.recommendation_score)).limit(limit)
        
        result = await self.db.execute(stmt)
        tutors = result.scalars().all()
        return [{"tutor_id": str(t.tutor_id), "score": t.recommendation_score} for t in tutors]

    async def get_tutor_metrics(self, tutor_id: UUID):
        metric = await self.db.get(TutorMetric, tutor_id)
        if not metric:
            return None
        return metric

    async def get_readiness_status(self) -> dict:
        status = {"postgres": "unhealthy", "redis": "unhealthy", "status": "degraded"}
        try:
            await self.db.execute(text("SELECT 1"))
            status["postgres"] = "healthy"
        except Exception:
            pass

        try:
            await self.redis.ping()
            status["redis"] = "healthy"
        except Exception:
            pass
            
        if status["postgres"] == "healthy" and status["redis"] == "healthy":
            status["status"] = "ok"
            
        return status

    async def trigger_recalculation(self, tutor_id: UUID | None = None):
        """
        Triggers score updates. In production, this would be a background task.
        """
        if tutor_id:
            tutors = [await self.db.get(TutorMetric, tutor_id)]
        else:
            result = await self.db.execute(select(TutorMetric))
            tutors = result.scalars().all()

        for tutor in tutors:
            if tutor:
                tutor.recommendation_score = await self.calculate_score(tutor)
        
        await self.db.commit()
        await self.refresh_cache("all")

    async def refresh_cache(self, target: str) -> int:
        """
        Clears Redis keys based on target.
        """
        keys_pattern = f"{self.cache_key_prefix}*"
        if target != "all":
            keys_pattern = f"{self.cache_key_prefix}{target}*"
            
        keys = await self.redis.keys(keys_pattern)
        if keys:
            await self.redis.delete(*keys)
        return len(keys)
