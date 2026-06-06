from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class PlatformSettingsResponse(BaseModel):
    """Schema for platform settings."""
    
    # Commission and pricing
    platform_commission_rate: float = Field(description="Platform commission percentage")
    minimum_session_price: float = Field(description="Minimum price per session")
    maximum_session_price: float = Field(description="Maximum price per session")
    
    # User limits
    max_sessions_per_day: int = Field(description="Maximum sessions per tutor per day")
    max_students_per_session: int = Field(description="Maximum students in group session")
    session_cancellation_hours: int = Field(description="Hours before session to allow cancellation")
    
    # Verification settings
    auto_approve_verified_tutors: bool = Field(description="Auto-approve sessions from verified tutors")
    verification_required_subjects: List[str] = Field(description="Subjects requiring verification")
    
    # Content moderation
    auto_moderation_enabled: bool = Field(description="Enable automatic content moderation")
    profanity_filter_enabled: bool = Field(description="Enable profanity filtering")
    
    # Notifications
    email_notifications_enabled: bool = Field(description="Enable email notifications")
    sms_notifications_enabled: bool = Field(description="Enable SMS notifications")
    
    # Maintenance
    maintenance_mode: bool = Field(description="Platform maintenance mode status")
    maintenance_message: Optional[str] = Field(description="Maintenance mode message")
    
    # Updated metadata
    last_updated_at: datetime
    last_updated_by: UUID
    last_updated_by_name: str


class PlatformSettingsUpdate(BaseModel):
    """Schema for updating platform settings."""
    
    platform_commission_rate: Optional[float] = None
    minimum_session_price: Optional[float] = None
    maximum_session_price: Optional[float] = None
    max_sessions_per_day: Optional[int] = None
    max_students_per_session: Optional[int] = None
    session_cancellation_hours: Optional[int] = None
    auto_approve_verified_tutors: Optional[bool] = None
    verification_required_subjects: Optional[List[str]] = None
    auto_moderation_enabled: Optional[bool] = None
    profanity_filter_enabled: Optional[bool] = None
    email_notifications_enabled: Optional[bool] = None
    sms_notifications_enabled: Optional[bool] = None


class ServiceHealth(BaseModel):
    """Schema for individual service health."""
    
    name: str
    status: str  # healthy, unhealthy, degraded
    response_time_ms: float
    last_check: datetime
    error_rate: float
    uptime_percentage: float


class DatabaseHealth(BaseModel):
    """Schema for database health."""
    
    name: str
    type: str  # postgresql, mongodb, redis
    status: str  # connected, disconnected, slow
    connection_count: int
    response_time_ms: float
    last_check: datetime


class SystemHealthResponse(BaseModel):
    """Schema for comprehensive system health."""
    
    overall_status: str  # healthy, degraded, unhealthy
    services: List[ServiceHealth]
    databases: List[DatabaseHealth]
    kafka_status: str
    redis_status: str
    disk_usage_percentage: float
    memory_usage_percentage: float
    cpu_usage_percentage: float
    last_updated: datetime


class ServiceStatusResponse(BaseModel):
    """Schema for detailed service status."""
    
    services: Dict[str, Dict[str, Any]]
    total_services: int
    healthy_services: int
    unhealthy_services: int
    last_updated: datetime


class SystemStatsResponse(BaseModel):
    """Schema for system performance statistics."""
    
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, float]
    active_connections: int
    requests_per_minute: float
    error_rate: float
    average_response_time: float
    uptime_seconds: int
    last_updated: datetime


class MaintenanceRequest(BaseModel):
    """Schema for maintenance mode request."""
    
    message: str = Field(description="Maintenance message to display to users")
    estimated_duration_minutes: Optional[int] = Field(None, description="Estimated maintenance duration")


class BackupRequest(BaseModel):
    """Schema for backup creation request."""
    
    backup_type: str = Field(description="Type: full, incremental, database_only")
    include_files: bool = Field(default=False, description="Include uploaded files in backup")
    description: Optional[str] = Field(None, description="Backup description")