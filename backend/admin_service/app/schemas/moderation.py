from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ReportResponse(BaseModel):
    id: UUID
    reporter_id: UUID
    reported_id: UUID
    report_type: str
    status: str
    description: str | None = None
    evidence: list[Any] = []
    created_at: datetime
    resolved_at: datetime | None = None
    resolution_notes: str | None = None


class ReportListResponse(BaseModel):
    reports: list[ReportResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class ReportActionRequest(BaseModel):
    action_taken: str
    notes: str | None = None


class ModerationStats(BaseModel):
    pending_reports: int
    resolved_today: int
    dismissed_today: int
    total_open: int


class ContentModerationRequest(BaseModel):
    reason: str
    action: str | None = None


class FlaggedMessage(BaseModel):
    id: UUID
    group_id: UUID
    sender_id: UUID
    content: str
    severity: str
    flagged_at: datetime


class ChatModerationResponse(BaseModel):
    messages: list[FlaggedMessage]
    total: int
    page: int
    per_page: int
    total_pages: int
