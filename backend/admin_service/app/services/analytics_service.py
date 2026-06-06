from __future__ import annotations

import json
import logging

from redis.asyncio import Redis

from app.core.config import Settings
from app.kafka.producer import AdminKafkaProducer
from app.repositories.analytics_repo import AnalyticsRepository
from app.repositories.audit_repo import AuditRepository
from app.repositories.user_repo import UserRepository
from app.schemas.analytics import DashboardOverview

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for dashboard analytics and metrics."""

    def __init__(
        self,
        user_repo: UserRepository,
        analytics_repo: AnalyticsRepository,
        audit_repo: AuditRepository,
        redis: Redis,
        kafka_producer: AdminKafkaProducer,
        settings: Settings,
    ):
        self.user_repo = user_repo
        self.analytics_repo = analytics_repo
        self.audit_repo = audit_repo
        self.redis = redis
        self.kafka_producer = kafka_producer
        self.settings = settings

    async def get_dashboard_overview(self) -> DashboardOverview:
        """Get dashboard overview metrics with caching."""
        cache_key = "admin:dashboard:overview"

        # Try to get from cache
        cached = await self.redis.get(cache_key)
        if cached:
            return DashboardOverview.model_validate(json.loads(cached))

        # Fetch metrics from repos
        platform_revenue = await self.analytics_repo.fetch_platform_revenue()

        overview = DashboardOverview(
            total_users=await self.user_repo.count_total_users(),
            total_tutors=await self.user_repo.count_total_tutors(),
            total_students=await self.user_repo.count_total_students(),
            active_users_today=await self.user_repo.count_active_users_today(),
            total_sessions=await self.analytics_repo.count_total_sessions(),
            total_groups=await self.analytics_repo.count_total_groups(),
            completed_sessions=await self.analytics_repo.count_completed_sessions(),
            total_revenue=platform_revenue / 0.1 if platform_revenue > 0 else 0.0,
            platform_revenue=platform_revenue,
            pending_verifications=await self.user_repo.count_pending_verifications(),
            active_reports=0,
        )

        # Cache for 5 minutes
        await self.redis.setex(
            cache_key,
            self.settings.analytics_cache_ttl_seconds,
            json.dumps(overview.model_dump()),
        )

        return overview