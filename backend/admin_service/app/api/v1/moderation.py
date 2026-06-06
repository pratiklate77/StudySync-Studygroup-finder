from __future__ import annotations

from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_admin_service, get_current_admin, require_permission
from app.models.admin_user import AdminUser
from app.schemas.moderation import (
    ReportListResponse,
    ReportResponse,
    ReportActionRequest,
    ModerationStats,
    ContentModerationRequest,
    ChatModerationResponse,
)
from app.services.admin_service import AdminService

router = APIRouter()


@router.get("/reports", response_model=ReportListResponse)
async def get_reports(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_reports"))],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, description="Filter by status: pending, resolved, dismissed"),
    report_type: str | None = Query(None, description="Filter by type: user, chat, session"),
) -> ReportListResponse:
    """
    Get user reports and complaints.
    
    Returns paginated list of reports with filtering options.
    """
    reports, total = await admin_service.get_reports(
        page=page,
        per_page=per_page,
        status_filter=status_filter,
        report_type=report_type,
    )
    
    return ReportListResponse(
        reports=reports,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.get("/reports/stats", response_model=ModerationStats)
async def get_moderation_stats(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_reports"))],
) -> ModerationStats:
    """
    Get moderation statistics.
    
    Returns counts of pending reports, resolved cases, and trends.
    """
    return await admin_service.get_moderation_stats()


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report_details(
    report_id: UUID,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_reports"))],
) -> ReportResponse:
    """
    Get detailed report information.
    
    Returns complete report data including evidence and context.
    """
    report = await admin_service.get_report_details(report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    return report


@router.post("/reports/{report_id}/resolve")
async def resolve_report(
    report_id: UUID,
    action_data: ReportActionRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("resolve_reports"))],
) -> dict[str, str]:
    """
    Resolve a user report.
    
    Takes action on the reported content/user and marks report as resolved.
    """
    success = await admin_service.resolve_report(
        report_id=report_id,
        admin_id=current_admin.id,
        action_taken=action_data.action_taken,
        resolution_notes=action_data.notes,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or already resolved"
        )
    
    return {"message": "Report resolved successfully"}


@router.post("/reports/{report_id}/dismiss")
async def dismiss_report(
    report_id: UUID,
    action_data: ReportActionRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("resolve_reports"))],
) -> dict[str, str]:
    """
    Dismiss a report as invalid.
    
    Marks report as dismissed without taking action.
    """
    success = await admin_service.dismiss_report(
        report_id=report_id,
        admin_id=current_admin.id,
        reason=action_data.notes or "Report dismissed by admin",
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or already processed"
        )
    
    return {"message": "Report dismissed"}


@router.get("/chat/messages")
async def get_flagged_messages(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("moderate_content"))],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    severity: str | None = Query(None, description="Filter by severity: low, medium, high"),
) -> ChatModerationResponse:
    """
    Get flagged chat messages for moderation.
    
    Returns messages flagged by automated systems or user reports.
    """
    return await admin_service.get_flagged_messages(
        page=page,
        per_page=per_page,
        severity=severity,
    )


@router.post("/chat/messages/{message_id}/delete")
async def delete_chat_message(
    message_id: UUID,
    action_data: ContentModerationRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("delete_content"))],
) -> dict[str, str]:
    """
    Delete inappropriate chat message.
    
    Removes message from chat history and logs moderation action.
    """
    success = await admin_service.delete_chat_message(
        message_id=message_id,
        admin_id=current_admin.id,
        reason=action_data.reason,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found or already deleted"
        )
    
    return {"message": "Chat message deleted"}


@router.post("/chat/messages/{message_id}/warn")
async def warn_message_sender(
    message_id: UUID,
    action_data: ContentModerationRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("moderate_content"))],
) -> dict[str, str]:
    """
    Send warning to message sender.
    
    Issues warning without deleting content.
    """
    success = await admin_service.warn_user_for_message(
        message_id=message_id,
        admin_id=current_admin.id,
        warning_reason=action_data.reason,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    return {"message": "Warning sent to user"}


@router.get("/sessions/reported")
async def get_reported_sessions(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_reports"))],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> dict:
    """
    Get reported tutoring sessions.
    
    Returns sessions reported for inappropriate behavior or issues.
    """
    return await admin_service.get_reported_sessions(
        page=page,
        per_page=per_page,
    )


@router.post("/sessions/{session_id}/cancel")
async def cancel_session(
    session_id: UUID,
    action_data: ContentModerationRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("cancel_sessions"))],
) -> dict[str, str]:
    """
    Cancel a tutoring session.
    
    Cancels session and handles refunds if applicable.
    """
    success = await admin_service.cancel_session(
        session_id=session_id,
        admin_id=current_admin.id,
        reason=action_data.reason,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or cannot be cancelled"
        )
    
    return {"message": "Session cancelled successfully"}


@router.post("/bulk-moderate")
async def bulk_moderate_content(
    content_ids: List[UUID],
    action_data: ContentModerationRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("delete_content"))],
) -> dict[str, int]:
    """
    Bulk moderate multiple content items.
    
    Applies moderation action to multiple items at once.
    """
    if len(content_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot moderate more than 100 items at once"
        )
    
    moderated_count = await admin_service.bulk_moderate_content(
        content_ids=content_ids,
        admin_id=current_admin.id,
        action=action_data.action,
        reason=action_data.reason,
    )
    
    return {
        "message": f"Moderated {moderated_count} items",
        "moderated_count": moderated_count,
        "total_requested": len(content_ids),
    }