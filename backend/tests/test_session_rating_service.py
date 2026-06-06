import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "session_service"))
sys.path.insert(0, os.path.join(ROOT, "session_service", "app"))

from app.models.rating import Rating
from app.schemas.rating import RatingSubmit
from app.services.rating_service import RatingService
from app.models.session import SessionStatus


class TestRatingService(unittest.IsolatedAsyncioTestCase):
    async def test_submit_returns_rating_and_publishes_event(self):
        session_id = uuid4()
        student_id = uuid4()
        tutor_id = uuid4()

        fake_session = MagicMock()
        fake_session.participants = [student_id]
        fake_session.host_id = tutor_id
        fake_session.status = SessionStatus.completed

        ratings_repo = AsyncMock()
        ratings_repo.exists.return_value = False
        created_rating = Rating(
            session_id=session_id,
            tutor_id=tutor_id,
            student_id=student_id,
            score=5,
            comment="Excellent",
        )
        ratings_repo.create.return_value = created_rating

        sessions_repo = AsyncMock()
        sessions_repo.get_by_id.return_value = fake_session
        sessions_repo.increment_rating_aggregate.return_value = MagicMock(
            avg_rating=5.0,
            total_ratings=1,
        )

        service = RatingService.__new__(RatingService)
        service._ratings = ratings_repo
        service._sessions = sessions_repo

        producer = AsyncMock()
        producer.publish.return_value = True
        settings = MagicMock(kafka_rating_events_topic="RATING_EVENTS")

        payload = RatingSubmit(score=5, comment="Excellent")
        result = await service.submit(
            session_id=session_id,
            student_id=student_id,
            data=payload,
            producer=producer,
            settings=settings,
        )

        self.assertEqual(result.score, 5)
        self.assertEqual(result.comment, "Excellent")
        ratings_repo.create.assert_awaited_once()
        sessions_repo.increment_rating_aggregate.assert_awaited_once_with(session_id, 5)
        producer.publish.assert_awaited_once()

    async def test_submit_duplicate_rating_raises_conflict(self):
        session_id = uuid4()
        student_id = uuid4()

        fake_session = MagicMock()
        fake_session.participants = [student_id]
        fake_session.status = SessionStatus.completed

        ratings_repo = AsyncMock()
        ratings_repo.exists.return_value = True

        sessions_repo = AsyncMock()
        sessions_repo.get_by_id.return_value = fake_session

        service = RatingService.__new__(RatingService)
        service._ratings = ratings_repo
        service._sessions = sessions_repo

        producer = AsyncMock()
        settings = MagicMock(kafka_rating_events_topic="RATING_EVENTS")

        payload = RatingSubmit(score=4, comment="Good")
        with self.assertRaises(Exception) as ctx:
            await service.submit(
                session_id=session_id,
                student_id=student_id,
                data=payload,
                producer=producer,
                settings=settings,
            )

        self.assertIn("already rated", str(ctx.exception).lower())
        producer.publish.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
