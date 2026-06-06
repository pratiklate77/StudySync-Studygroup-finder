from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DashboardOverview(BaseModel):
    """Dashboard overview metrics."""
    total_users: int
    total_tutors: int
    total_students: int
    active_users_today: int
    total_sessions: int
    total_groups: int = 0
    completed_sessions: int
    total_revenue: float
    platform_revenue: float = 0.0  # Sum of platform_fee (10% commission)
    pending_verifications: int
    active_reports: int


class UserAnalytics(BaseModel):
    """User analytics data."""
    total_registrations: int
    registrations_today: int
    registrations_this_week: int
    registrations_this_month: int
    active_users_today: int
    active_users_this_week: int
    
    # Registration trends (last 30 days)
    registration_trend: list[dict[str, Any]]  # [{date: "2024-01-01", count: 5}, ...]


class SessionAnalytics(BaseModel):
    """Session analytics data."""
    total_sessions: int
    completed_sessions: int
    cancelled_sessions: int
    completion_rate: float
    average_session_duration: float | None
    sessions_today: int
    sessions_this_week: int
    sessions_this_month: int
    
    # Session trends
    session_trend: list[dict[str, Any]]


class RevenueAnalytics(BaseModel):
    """Revenue analytics data."""
    total_revenue: float
    revenue_today: float
    revenue_this_week: float
    revenue_this_month: float
    average_session_value: float
    platform_commission: float
    
    # Revenue trends
    revenue_trend: list[dict[str, Any]]


class TutorAnalytics(BaseModel):
    """Tutor analytics data."""
    total_tutors: int
    verified_tutors: int
    pending_verifications: int
    rejected_verifications: int
    average_tutor_rating: float
    top_subjects: list[dict[str, Any]]  # [{subject: "Math", count: 25}, ...]


class PlatformHealth(BaseModel):
    """Platform health metrics."""
    api_response_time: float
    database_connections: int
    redis_status: str
    kafka_status: str
    error_rate: float
    uptime_percentage: float