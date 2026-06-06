from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, Request, Depends

from app.schemas.verification import (
    AdminApproveRequest,
    AdminRejectRequest,
    AdminReviewRequest,
    AdminVerificationDetail,
    AdminVerificationListResponse,
)
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

_ADMIN_ROLES = {"admin", "super_admin"}


def _require_platform_admin(user=Depends(get_current_user)) -> uuid.UUID:
    """Require a valid Admin Service JWT (super_admin / admin / moderator)."""
    role = getattr(user, "role", "user")
    if role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Platform admin access required")
    return user.id


@router.get(
    "/",
    response_model=AdminVerificationListResponse,
)
async def list_verifications(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="Filter by status: pending, under_review, verified, rejected"),
    admin_id: uuid.UUID = Depends(_require_platform_admin),
) -> AdminVerificationListResponse:
    """List all tutor verification requests with optional status filter."""
    service = request.app.state.admin_verification_service
    return await service.list_requests(page=page, per_page=per_page, status=status)


@router.get(
    "/pending",
    response_model=AdminVerificationListResponse,
)
async def list_pending_verifications(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    admin_id: uuid.UUID = Depends(_require_platform_admin),
) -> AdminVerificationListResponse:
    """List pending tutor verification requests."""
    service = request.app.state.admin_verification_service
    return await service.list_requests(page=page, per_page=per_page, status="PENDING")


@router.get(
    "/{request_id}",
    response_model=AdminVerificationDetail,
)
async def get_verification_detail(
    request_id: uuid.UUID,
    request: Request,
    admin_id: uuid.UUID = Depends(_require_platform_admin),
) -> AdminVerificationDetail:
    """Get detailed tutor verification request."""
    service = request.app.state.admin_verification_service
    detail = await service.get_verification_detail(request_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Verification request not found")
    return detail


@router.post("/{request_id}/review")
async def mark_under_review(
    request_id: uuid.UUID,
    body: AdminReviewRequest,
    request: Request,
    admin_id: uuid.UUID = Depends(_require_platform_admin),
) -> dict[str, str]:
    """Mark a pending tutor verification request as under review."""
    service = request.app.state.admin_verification_service
    success = await service.mark_under_review(
        request_id=request_id,
        admin_id=admin_id,
        admin_notes=body.admin_notes,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Request not found or not in pending status")
    return {"message": "Verification marked as under review"}


@router.post("/{request_id}/approve")
async def approve_verification(
    request_id: uuid.UUID,
    body: AdminApproveRequest,
    request: Request,
    admin_id: uuid.UUID = Depends(_require_platform_admin),
) -> dict[str, str]:
    """Approve a tutor verification request. Publishes TUTOR_VERIFIED event."""
    service = request.app.state.admin_verification_service
    success = await service.approve_request(
        request_id=request_id,
        admin_id=admin_id,
        admin_notes=body.admin_notes,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Request not found or already finalized")
    return {"message": "Verification approved"}


@router.post("/{request_id}/reject")
async def reject_verification(
    request_id: uuid.UUID,
    body: AdminRejectRequest,
    request: Request,
    admin_id: uuid.UUID = Depends(_require_platform_admin),
) -> dict[str, str]:
    """Reject a tutor verification request. Publishes TUTOR_REJECTED event."""
    service = request.app.state.admin_verification_service
    success = await service.reject_request(
        request_id=request_id,
        admin_id=admin_id,
        reason=body.reason,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Request not found or already finalized")
    return {"message": "Verification rejected"}