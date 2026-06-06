from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, DECIMAL, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class PaymentStatus(str):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    tutor_id = Column(UUID(as_uuid=True), nullable=False)
    session_id = Column(UUID(as_uuid=True), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    platform_fee = Column(DECIMAL(10, 2), nullable=False)
    status = Column(String(length=20), nullable=False, default=PaymentStatus.PENDING)
    payment_method = Column(String(length=50), nullable=False)
    provider_id = Column(String(length=255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
