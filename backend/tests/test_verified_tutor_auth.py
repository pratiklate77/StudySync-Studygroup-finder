"""
Tests for verified tutor authorization in session creation.

Tests verify:
1. Verified tutor can create session
2. Unverified user cannot create session (403)
3. Rejected tutor cannot create session (403)
4. Suspended tutor cannot create session (403)
5. TUTOR_VERIFIED Kafka event updates read model
6. TUTOR_REJECTED Kafka event updates read model
7. TUTOR_SUSPENDED Kafka event updates read model
"""

import os
import sys
import unittest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "session_service"))
sys.path.insert(0, os.path.join(ROOT, "session_service", "app"))

from app.models.verified_tutor import VerifiedTutor
from app.repositories.verified_tutor_repository import VerifiedTutorRepository
from app.services.session_service import SessionService
from app.models.session import SessionType, SessionStatus


class TestVerifiedTutorRepository(unittest.IsolatedAsyncioTestCase):
    """Tests for VerifiedTutorRepository read model operations."""

    async def asyncSetUp(self):
        self.db = AsyncMock()
        self.col = AsyncMock()
        self.db.__getitem__.return_value = self.col
        self.repo = VerifiedTutorRepository(self.db)

    async def test_upsert_verified_creates_document(self):
        """TUTOR_VERIFIED upserts document with correct fields."""
        user_id = uuid4()
        await self.repo.upsert_verified(user_id, subjects=["Math", "Physics"])

        call_args = self.col.update_one.call_args
        filter_, update, upsert_opt = call_args[0][0], call_args[0][1], call_args[1]

        self.assertEqual(filter_, {"user_id": str(user_id)})
        self.assertIn("$set", update)
        self.assertEqual(update["$set"]["is_verified"], True)
        self.assertEqual(update["$set"]["status"], "active")
        self.assertEqual(update["$set"]["subjects"], ["Math", "Physics"])
        self.assertTrue(upsert_opt.get("upsert", False))

    async def test_mark_rejected_sets_fields(self):
        """TUTOR_REJECTED marks tutor as rejected."""
        user_id = uuid4()
        await self.repo.mark_rejected(user_id)

        call_args = self.col.update_one.call_args
        filter_, update, upsert_opt = call_args[0][0], call_args[0][1], call_args[1]

        self.assertEqual(filter_, {"user_id": str(user_id)})
        self.assertEqual(update["$set"]["is_verified"], False)
        self.assertEqual(update["$set"]["status"], "rejected")
        self.assertTrue(upsert_opt.get("upsert", False))

    async def test_mark_suspended_sets_fields(self):
        """TUTOR_SUSPENDED marks tutor as suspended."""
        user_id = uuid4()
        await self.repo.mark_suspended(user_id)

        call_args = self.col.update_one.call_args
        filter_, update, upsert_opt = call_args[0][0], call_args[0][1], call_args[1]

        self.assertEqual(filter_, {"user_id": str(user_id)})
        self.assertEqual(update["$set"]["is_verified"], False)
        self.assertEqual(update["$set"]["status"], "suspended")
        self.assertTrue(upsert_opt.get("upsert", False))

    async def test_is_verified_returns_true_for_active_verified(self):
        """is_verified() returns True when document matches all conditions."""
        self.col.find_one.return_value = {"_id": "some-id"}
        result = await self.repo.is_verified(uuid4())
        self.assertTrue(result)

    async def test_is_verified_returns_false_when_not_found(self):
        """is_verified() returns False when no matching document."""
        self.col.find_one.return_value = None
        result = await self.repo.is_verified(uuid4())
        self.assertFalse(result)

    async def test_is_verified_queries_with_all_conditions(self):
        """is_verified() must query with user_id + is_verified + status=active."""
        user_id = uuid4()
        self.col.find_one.return_value = {"_id": "some-id"}
        await self.repo.is_verified(user_id)

        self.col.find_one.assert_called_once_with(
            {"user_id": str(user_id), "is_verified": True, "status": "active"},
            projection={"_id": 1},
        )


class TestSessionCreateAuthorization(unittest.IsolatedAsyncioTestCase):
    """Tests that session creation enforces verified tutor check."""

    async def asyncSetUp(self):
        self.db = AsyncMock()
        self.sessions_repo = AsyncMock()
        self.verified_tutors_repo = AsyncMock()
        self.service = SessionService.__new__(SessionService)
        self.service._sessions = self.sessions_repo  # type: ignore[attr-defined]
        self.service._verified_tutors = self.verified_tutors_repo  # type: ignore[attr-defined]

    def _make_create_payload(self, session_type=SessionType.free):
        from app.schemas.session import SessionCreate, LocationIn

        return SessionCreate(
            title="Test Session",
            description="A test",
            session_type=session_type,
            price=0.0,
            max_participants=10,
            scheduled_time=datetime.now(UTC),
            location=LocationIn(longitude=0.0, latitude=0.0),
            subject_tags=["Math"],
        )

    async def test_verified_tutor_can_create_session(self):
        """Verified, active tutor can create a session."""
        self.verified_tutors_repo.is_verified.return_value = True
        host_id = uuid4()
        payload = self._make_create_payload()

        await self.service.create_session(host_id=host_id, data=payload)

        self.sessions_repo.create.assert_awaited_once()

    async def test_unverified_user_cannot_create_session(self):
        """Unverified user gets 403 when trying to create a session."""
        self.verified_tutors_repo.is_verified.return_value = False
        host_id = uuid4()
        payload = self._make_create_payload()

        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            await self.service.create_session(host_id=host_id, data=payload)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Only verified tutors can create sessions", ctx.exception.detail)
        self.sessions_repo.create.assert_not_awaited()

    async def test_rejected_tutor_cannot_create_session(self):
        """Rejected tutor (status=rejected) gets 403."""
        self.verified_tutors_repo.is_verified.return_value = False
        host_id = uuid4()
        payload = self._make_create_payload()

        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            await self.service.create_session(host_id=host_id, data=payload)

        self.assertEqual(ctx.exception.status_code, 403)

    async def test_suspended_tutor_cannot_create_session(self):
        """Suspended tutor (status=suspended) gets 403."""
        self.verified_tutors_repo.is_verified.return_value = False
        host_id = uuid4()
        payload = self._make_create_payload()

        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            await self.service.create_session(host_id=host_id, data=payload)

        self.assertEqual(ctx.exception.status_code, 403)

    async def test_paid_session_still_requires_verification(self):
        """Paid sessions also require verified tutor (same check applies)."""
        self.verified_tutors_repo.is_verified.return_value = True
        host_id = uuid4()
        payload = self._make_create_payload(session_type=SessionType.paid)

        await self.service.create_session(host_id=host_id, data=payload)

        self.sessions_repo.create.assert_awaited_once()

    async def test_verified_tutor_check_called_with_correct_user_id(self):
        """is_verified is called with the host user's UUID."""
        self.verified_tutors_repo.is_verified.return_value = True
        host_id = uuid4()
        payload = self._make_create_payload()

        await self.service.create_session(host_id=host_id, data=payload)

        self.verified_tutors_repo.is_verified.assert_awaited_once_with(host_id)


class TestVerifiedTutorModel(unittest.TestCase):
    """Tests for VerifiedTutor Pydantic model."""

    def test_defaults(self):
        """VerifiedTutor defaults to is_verified=True, status=active."""
        vt = VerifiedTutor(user_id=uuid4())
        self.assertTrue(vt.is_verified)
        self.assertEqual(vt.status, "active")
        self.assertIsInstance(vt.subjects, list)
        self.assertEqual(len(vt.subjects), 0)
        self.assertIsNone(vt.verified_at)

    def test_rejected_state(self):
        """Rejected tutor has is_verified=False, status=rejected."""
        vt = VerifiedTutor(user_id=uuid4(), is_verified=False, status="rejected")
        self.assertFalse(vt.is_verified)
        self.assertEqual(vt.status, "rejected")

    def test_suspended_state(self):
        """Suspended tutor has is_verified=False, status=suspended."""
        vt = VerifiedTutor(user_id=uuid4(), is_verified=False, status="suspended")
        self.assertFalse(vt.is_verified)
        self.assertEqual(vt.status, "suspended")


if __name__ == "__main__":
    unittest.main()