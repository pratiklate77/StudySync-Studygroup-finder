from datetime import UTC, datetime
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.verified_tutor import VerifiedTutor


class VerifiedTutorRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db["verified_tutors"]

    async def upsert_pending(self, user_id: UUID) -> None:
        """Insert a pending tutor record so they can create free sessions."""
        now = datetime.now(UTC)
        await self._col.update_one(
            {"user_id": str(user_id)},
            {
                "$setOnInsert": {
                    "user_id": str(user_id),
                    "is_verified": False,
                    "status": "pending",
                    "created_at": now,
                    "updated_at": now,
                },
            },
            upsert=True,
        )

    async def upsert_verified(self, user_id: UUID, subjects: list[str] | None = None) -> None:
        """Idempotent upsert — marks user as verified, active tutor."""
        now = datetime.now(UTC)
        set_fields: dict = {
            "user_id": str(user_id),
            "is_verified": True,
            "status": "active",
            "verified_at": now,
            "updated_at": now,
        }
        if subjects is not None:
            set_fields["subjects"] = subjects

        await self._col.update_one(
            {"user_id": str(user_id)},
            {
                "$set": set_fields,
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    async def mark_rejected(self, user_id: UUID) -> None:
        """Mark tutor as rejected — is_verified=false, status=rejected."""
        await self._col.update_one(
            {"user_id": str(user_id)},
            {
                "$set": {
                    "user_id": str(user_id),
                    "is_verified": False,
                    "status": "rejected",
                    "updated_at": datetime.now(UTC),
                },
                "$setOnInsert": {"created_at": datetime.now(UTC)},
            },
            upsert=True,
        )

    async def mark_suspended(self, user_id: UUID) -> None:
        """Mark tutor as suspended — is_verified=false, status=suspended."""
        await self._col.update_one(
            {"user_id": str(user_id)},
            {
                "$set": {
                    "user_id": str(user_id),
                    "is_verified": False,
                    "status": "suspended",
                    "updated_at": datetime.now(UTC),
                },
                "$setOnInsert": {"created_at": datetime.now(UTC)},
            },
            upsert=True,
        )

    async def is_verified(self, user_id: UUID) -> bool:
        """Check if user is a verified, active tutor.

        Only returns True when ALL conditions are satisfied:
          - document exists
          - is_verified == True
          - status == "active"
        """
        doc = await self._col.find_one(
            {"user_id": str(user_id), "is_verified": True, "status": "active"},
            projection={"_id": 1},
        )
        return doc is not None

    async def has_tutor_record(self, user_id: UUID) -> bool:
        """Check if any tutor record exists for this user (verified or pending)."""
        doc = await self._col.find_one(
            {"user_id": str(user_id)},
            projection={"_id": 1},
        )
        return doc is not None