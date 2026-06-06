from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, String, UUID as SQLUUID
from sqlalchemy.orm import relationship

from app.models.base import Base
from .enums import DocumentType

class VerificationDocument(Base):
    """Document model associated with a TutorVerificationRequest.

    Attributes:
        id: Primary key UUID.
        request_id: Foreign key to TutorVerificationRequest.
        file_name: Original file name uploaded.
        file_url: URL or path where the document is stored.
        document_type: Type of the document (e.g., IDENTITY_PROOF).
        uploaded_at: Timestamp of upload.
    """
    __tablename__ = "verification_documents"

    id: uuid.UUID = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: uuid.UUID = Column(SQLUUID(as_uuid=True), ForeignKey("tutor_verification_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name: str = Column(String(255), nullable=False)
    file_url: str = Column(String(500), nullable=False)
    document_type: str = Column(String(50), nullable=False)  # Should correspond to DocumentType enum values
    uploaded_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationship back to the verification request
    request = relationship("TutorVerificationRequest", back_populates="documents")

    def __repr__(self) -> str:
        return f"<VerificationDocument id={self.id} type={self.document_type}>"
