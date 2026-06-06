from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentBase(BaseModel):
    file_name: str
    file_url: str
    document_type: str


class DocumentResponse(DocumentBase):
    id: uuid.UUID
    verification_request_id: uuid.UUID
    uploaded_at: datetime


class DocumentUploadRequest(BaseModel):
    """Schema for uploading a document to an existing verification request."""
    request_type: str = Field(..., description="Must match the existing pending request type")
    file_name: str = Field(..., min_length=1)
    file_url: str = Field(..., min_length=1)
    document_type: str = Field(..., description="e.g. id_proof, certificate, background_report")


class VerificationRequestSubmit(BaseModel):
    request_type: str = Field(..., description="identity, education, or background_check")


class VerificationRequestResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    request_type: str
    status: str
    admin_notes: Optional[str] = None
    reviewed_by: Optional[uuid.UUID] = None
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    documents: list[DocumentResponse] = []

    class Config:
        from_attributes = True


class VerificationStatusResponse(BaseModel):
    user_id: uuid.UUID
    request_id: uuid.UUID
    request_type: str
    status: str
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    admin_notes: Optional[str] = None
    document_count: int


class VerificationHistoryResponse(BaseModel):
    """All verification requests for a user across all time."""
    user_id: uuid.UUID
    total: int
    requests: list[VerificationRequestResponse]


# Admin Schemas

class AdminVerificationListItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    request_type: str
    status: str
    submitted_at: datetime
    document_count: int


class AdminVerificationListResponse(BaseModel):
    """Paginated list of verification requests for admin."""
    items: list[AdminVerificationListItem]
    total: int
    page: int
    per_page: int
    total_pages: int


class AdminVerificationDetail(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    request_type: str
    status: str
    documents: list[DocumentResponse]
    submitted_at: datetime
    admin_notes: Optional[str] = None
    reviewed_by: Optional[uuid.UUID] = None
    reviewed_at: Optional[datetime] = None


class AdminApproveRequest(BaseModel):
    admin_notes: Optional[str] = None


class AdminRejectRequest(BaseModel):
    reason: str = Field(..., description="Reason for rejection")


class AdminReviewRequest(BaseModel):
    """Mark a request as under_review."""
    admin_notes: Optional[str] = None
