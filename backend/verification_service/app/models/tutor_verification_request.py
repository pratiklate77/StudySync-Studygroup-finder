from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from .enums import VerificationStatus

class TutorVerificationRequest(Base):
    __tablename__ = "tutor_verification_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
   
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),nullable=False,index=True
    )
    
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status", native_enum=False),
        nullable=False,
        default=VerificationStatus.PENDING,
    )
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subjects: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # CSV list
    experience_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hourly_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    documents: Mapped[List["VerificationDocument"]] = relationship(
        "VerificationDocument", back_populates="request", cascade="all, delete-orphan"
    )
