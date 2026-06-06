import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class TutorMetric(Base):
    __tablename__ = "tutor_metrics"

    tutor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    average_rating: Mapped[float] = mapped_column(Float, default=0.0)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    total_sessions: Mapped[int] = mapped_column(Integer, default=0)
    sessions_completed: Mapped[int] = mapped_column(Integer, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    subjects: Mapped[list[str]] = mapped_column(JSONB, default=list)
    activity_score: Mapped[float] = mapped_column(Float, default=0.0)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    last_activity: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

class RecommendationScore(Base):
    __tablename__ = "recommendation_scores"

    tutor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    subject: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class TrendingTutor(Base):
    __tablename__ = "trending_tutors"

    tutor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    growth_rate: Mapped[float] = mapped_column(Float, default=0.0) # growth in sessions/ratings
    trend_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # This model would be updated by Kafka Consumers
