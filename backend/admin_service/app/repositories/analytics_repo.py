from __future__ import annotations

import logging

from sqlalchemy import text

from app.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class AnalyticsRepository:
    """Repository for cross-DB analytics aggregation."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def fetch_platform_revenue(self) -> float:
        """Sum platform_fee from completed payments."""
        try:
            async with self.db_manager.PaymentSessionLocal() as psession:
                result = await psession.execute(
                    text(
                        "SELECT COALESCE(SUM(platform_fee), 0) FROM payments WHERE status = 'completed'"
                    )
                )
                return float(result.scalar() or 0)
        except Exception:
            return 0.0

    async def count_total_groups(self) -> int:
        """Count all study groups from Group PostgreSQL."""
        try:
            async with self.db_manager.GroupSessionLocal() as session:
                result = await session.execute(text("SELECT COUNT(*) FROM groups"))
                return int(result.scalar() or 0)
        except Exception:
            return 0

    async def count_total_sessions(self) -> int:
        """Count all sessions from MongoDB (session service)."""
        try:
            count = await self.db_manager.session_db.sessions.count_documents({})
            return count
        except Exception:
            return 0

    async def count_completed_sessions(self) -> int:
        """Count completed sessions from MongoDB."""
        try:
            count = await self.db_manager.session_db.sessions.count_documents({
                "status": "completed"
            })
            return count
        except Exception:
            return 0