from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import Field

from app.models.base import BaseDocument


class VerifiedTutor(BaseDocument):
    """Local read-model populated by consuming TUTOR_VERIFIED / TUTOR_REJECTED / TUTOR_SUSPENDED Kafka events.

    This collection is the session service's authoritative source for whether a
    user may create sessions as a verified tutor.
    It is synchronised **only** via Kafka — no synchronous calls to Identity / Verification services.
    """

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID                       # user_id from Identity Service
    is_verified: bool = True
    status: str = "active"              # active | rejected | suspended
    verified_at: datetime | None = None
    subjects: list[str] = Field(default_factory=list)