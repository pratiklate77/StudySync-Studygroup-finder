from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VerificationRequest(BaseModel):
    """Schema for verification request data."""
    
    tutor_id: UUID
    subject: str
    qualification: str
    experience_years: int
    documents: List[str] = Field(description="List of document URLs")
    description: Optional[str] = None


class VerificationResponse(BaseModel):
    """Schema for verification response data."""
    
    id: UUID
    tutor_id: UUID
    tutor_name: str
    tutor_email: str
    subject: str
    qualification: str
    experience_years: int
    documents: List[str]
    description: Optional[str]
    status: str  # pending, approved, rejected
    submitted_at: datetime
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[UUID]
    reviewer_name: Optional[str]
    rejection_reason: Optional[str]
    admin_notes: Optional[str]


class VerificationListResponse(BaseModel):
    """Schema for paginated verification list."""
    
    verifications: List[VerificationResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class VerificationActionRequest(BaseModel):
    """Schema for verification action (approve/reject)."""
    
    reason: Optional[str] = Field(None, description="Reason for rejection (required for reject)")
    notes: Optional[str] = Field(None, description="Admin notes")


class VerificationStats(BaseModel):
    """Schema for verification statistics."""
    
    pending_count: int
    approved_count: int
    rejected_count: int
    total_count: int
    pending_by_subject: dict[str, int]
    average_review_time_hours: float
    approval_rate_percentage: float