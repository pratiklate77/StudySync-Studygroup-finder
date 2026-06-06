from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_admin_service, get_current_admin, require_permission
from app.models.admin_user import AdminUser
from app.schemas.analytics import DashboardOverview
from app.services.admin_service import AdminService

router = APIRouter()


@router.get("/overview", response_model=DashboardOverview)
async def get_dashboard_overview(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_analytics"))],
) -> DashboardOverview:
    """
    Get dashboard overview with key platform metrics.
    
    Returns:
    - Total users, tutors, students
    - Active users today
    - Total and completed sessions
    - Revenue metrics
    - Pending verifications and reports
    """
    return await admin_service.get_dashboard_overview()


@router.get("/users")
async def get_user_analytics(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_analytics"))],
):
    """
    Get detailed user analytics.
    
    Returns:
    - Registration trends
    - Active user metrics
    - User growth statistics
    """
    # Placeholder for detailed user analytics
    return {
        "message": "User analytics endpoint - to be implemented",
        "total_registrations": await admin_service._get_total_users(),
        "total_tutors": await admin_service._get_total_tutors(),
        "total_students": await admin_service._get_total_students(),
    }


@router.get("/sessions")
async def get_session_analytics(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_analytics"))],
):
    """
    Get session analytics and trends.
    
    Returns:
    - Session completion rates
    - Popular subjects and locations
    - Session duration statistics
    """
    # Placeholder for session analytics
    return {
        "message": "Session analytics endpoint - to be implemented",
        "total_sessions": await admin_service._get_total_sessions(),
        "completed_sessions": await admin_service._get_completed_sessions(),
    }


@router.get("/revenue")
async def get_revenue_analytics(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_analytics"))],
):
    """
    Get revenue analytics and financial metrics.
    
    Returns:
    - Total revenue and trends
    - Platform commission earnings
    - Payment success rates
    """
    # Placeholder for revenue analytics
    # Will be implemented when payment service is integrated
    return {
        "message": "Revenue analytics endpoint - to be implemented with payment service",
        "total_revenue": 0.0,
        "platform_commission": 0.0,
    }


@router.get("/platform-health")
async def get_platform_health(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_system_health"))],
):
    """
    Get platform health metrics.
    
    Returns:
    - Service status
    - Database connections
    - Error rates
    - System performance metrics
    """
    return await admin_service.get_system_health()