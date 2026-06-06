import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "recommendation_service"))
sys.path.insert(0, os.path.join(ROOT, "recommendation_service", "app"))

from app.services.recommendation_service import RecommendationService
from app.models.tutor_metric import TutorMetric
from app.core.config import Settings


class TestRecommendationService(unittest.IsolatedAsyncioTestCase):
    async def test_apply_session_rating_event_creates_new_metric(self):
        session = AsyncMock()
        session.get.return_value = None
        redis = AsyncMock()
        settings = Settings()

        service = RecommendationService(session, redis, settings)

        updated = await service.apply_session_rating_event(
            tutor_id=str(uuid4()),
            score=4,
            event_id="test-event",
            session_id="session-1",
            student_id="student-1",
        )

        self.assertTrue(updated)
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    async def test_apply_session_rating_event_updates_existing_metric(self):
        existing_metric = TutorMetric(
            tutor_id=uuid4(),
            average_rating=4.0,
            total_reviews=2,
            sessions_completed=2,
            activity_score=0.5,
        )

        session = AsyncMock()
        session.get.return_value = existing_metric
        redis = AsyncMock()
        settings = Settings()

        service = RecommendationService(session, redis, settings)

        updated = await service.apply_session_rating_event(
            tutor_id=str(existing_metric.tutor_id),
            score=5,
            event_id="test-event-2",
            session_id="session-2",
            student_id="student-2",
        )

        self.assertTrue(updated)
        self.assertAlmostEqual(existing_metric.average_rating, (4.0 * 2 + 5) / 3)
        self.assertEqual(existing_metric.total_reviews, 3)
        self.assertEqual(existing_metric.sessions_completed, 3)
        session.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
