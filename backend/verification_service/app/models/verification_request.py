import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, UUID as SQLUUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class VerificationRequest(Base, TimestampMixin):
    """Verification request model."""
    __tablename__ = "verification_requests"
    
    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(SQLUUID(as_uuid=True), nullable=False, index=True)
    request_type = Column(String(50), nullable=False)  # 'identity', 'education', 'background_check'
    status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected, under_review
    
    # Admin review
    admin_notes = Column(String(1000), nullable=True)
    reviewed_by = Column(SQLUUID(as_uuid=True), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Relationships
    documents = relationship("Document", back_populates="verification_request", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<VerificationRequest id={self.id} user_id={self.user_id} status={self.status}>"
