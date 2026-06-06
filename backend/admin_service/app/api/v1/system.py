from __future__ import annotations

from typing import Annotated, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_admin_service, get_current_admin, require_permission
from app.models.admin_user import AdminUser
from app.schemas.system import (
    PlatformSettingsResponse,
    PlatformSettingsUpdate,
    SystemHealthResponse,
    ServiceStatusResponse,
    MaintenanceRequest,
    BackupRequest,
    SystemStatsResponse,
)
from app.services.admin_service import AdminService

router = APIRouter()


@router.get("/settings", response_model=PlatformSettingsResponse)
async def get_platform_settings(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_settings"))],
) -> PlatformSettingsResponse:
    """
    Get current platform settings.
    
    Returns all configurable platform settings and their values.
    """
    return await admin_service.get_platform_settings()


@router.put("/settings", response_model=PlatformSettingsResponse)
async def update_platform_settings(
    settings_update: PlatformSettingsUpdate,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("manage_settings"))],
) -> PlatformSettingsResponse:
    """
    Update platform settings.
    
    Updates configurable platform settings like commission rates, limits, etc.
    """
    updated_settings = await admin_service.update_platform_settings(
        settings_update=settings_update,
        updated_by=current_admin.id,
    )
    
    return updated_settings


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_system_health"))],
) -> SystemHealthResponse:
    """
    Get comprehensive system health status.
    
    Returns health status of all services, databases, and external dependencies.
    """
    return await admin_service.get_system_health()


@router.get("/services", response_model=ServiceStatusResponse)
async def get_service_status(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_system_health"))],
) -> ServiceStatusResponse:
    """
    Get detailed status of all microservices.
    
    Returns individual service health, response times, and error rates.
    """
    return await admin_service.get_service_status()


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_system_health"))],
) -> SystemStatsResponse:
    """
    Get system performance statistics.
    
    Returns CPU, memory, disk usage, and other system metrics.
    """
    return await admin_service.get_system_stats()


@router.post("/maintenance")
async def enable_maintenance_mode(
    maintenance_request: MaintenanceRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("manage_maintenance"))],
) -> dict[str, str]:
    """
    Enable maintenance mode.
    
    Puts platform in maintenance mode with custom message.
    """
    success = await admin_service.enable_maintenance_mode(
        admin_id=current_admin.id,
        message=maintenance_request.message,
        estimated_duration=maintenance_request.estimated_duration_minutes,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to enable maintenance mode"
        )
    
    return {"message": "Maintenance mode enabled"}


@router.delete("/maintenance")
async def disable_maintenance_mode(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("manage_maintenance"))],
) -> dict[str, str]:
    """
    Disable maintenance mode.
    
    Restores normal platform operation.
    """
    success = await admin_service.disable_maintenance_mode(
        admin_id=current_admin.id,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to disable maintenance mode"
        )
    
    return {"message": "Maintenance mode disabled"}


@router.post("/backup")
async def create_system_backup(
    backup_request: BackupRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("manage_backups"))],
) -> dict[str, str]:
    """
    Create system backup.
    
    Initiates backup of specified databases and data.
    """
    backup_id = await admin_service.create_system_backup(
        admin_id=current_admin.id,
        backup_type=backup_request.backup_type,
        include_files=backup_request.include_files,
        description=backup_request.description,
    )
    
    return {
        "message": "Backup initiated successfully",
        "backup_id": str(backup_id),
    }


@router.get("/backups")
async def list_system_backups(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_backups"))],
) -> dict:
    """
    List available system backups.
    
    Returns list of all available backups with metadata.
    """
    return await admin_service.list_system_backups()


@router.post("/cache/clear")
async def clear_system_cache(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("manage_cache"))],
    cache_type: str | None = None,
) -> dict[str, str]:
    """
    Clear system cache.
    
    Clears Redis cache for better performance or troubleshooting.
    """
    cleared_keys = await admin_service.clear_system_cache(
        admin_id=current_admin.id,
        cache_type=cache_type,
    )
    
    return {
        "message": f"Cache cleared successfully",
        "cleared_keys": cleared_keys,
    }


@router.get("/logs")
async def get_system_logs(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_logs"))],
    service: str | None = None,
    level: str | None = None,
    limit: int = 100,
) -> dict:
    """
    Get system logs.
    
    Returns recent system logs with filtering options.
    """
    return await admin_service.get_system_logs(
        service=service,
        level=level,
        limit=limit,
    )


@router.get("/audit-trail")
async def get_audit_trail(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_audit_trail"))],
    admin_id: UUID | None = None,
    action_type: str | None = None,
    limit: int = 100,
) -> dict:
    """
    Get admin audit trail.
    
    Returns log of all admin actions for compliance and monitoring.
    """
    return await admin_service.get_audit_trail(
        admin_id=admin_id,
        action_type=action_type,
        limit=limit,
    )


@router.post("/notifications/broadcast")
async def broadcast_notification(
    notification_data: Dict[str, Any],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("send_notifications"))],
) -> dict[str, str]:
    """
    Broadcast system notification.
    
    Sends notification to all users or specific user groups.
    """
    notification_id = await admin_service.broadcast_notification(
        admin_id=current_admin.id,
        title=notification_data.get("title"),
        message=notification_data.get("message"),
        target_audience=notification_data.get("target_audience", "all"),
        priority=notification_data.get("priority", "normal"),
    )
    
    return {
        "message": "Notification broadcast successfully",
        "notification_id": str(notification_id),
    }