import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, UUID as SQLUUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class Document(Base, TimestampMixin):
    """Document model for verification requests."""
    __tablename__ = "documents"
    
    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_request_id = Column(
        SQLUUID(as_uuid=True),
        ForeignKey("verification_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    document_type = Column(String(50), nullable=False)  # 'id_proof', 'certificate', 'background_report', etc.
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    verification_request = relationship("VerificationRequest", back_populates="documents")
    
    def __repr__(self) -> str:
        return f"<Document id={self.id} type={self.document_type}>"
