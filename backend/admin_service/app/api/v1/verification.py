from __future__ import annotations

from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_admin_service, get_current_admin, require_permission
from app.models.admin_user import AdminUser
from app.schemas.verification import (
    VerificationListResponse,
    VerificationRequest,
    VerificationResponse,
    VerificationActionRequest,
    VerificationStats,
)
from app.services.admin_service import AdminService

router = APIRouter()


@router.get("/pending", response_model=VerificationListResponse)
async def get_pending_verifications(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_verifications"))],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    subject: str | None = Query(None, description="Filter by subject"),
) -> VerificationListResponse:
    """
    Get pending tutor verifications.
    
    Returns list of tutors waiting for verification approval.
    """
    verifications, total = await admin_service.get_pending_verifications(
        page=page,
        per_page=per_page,
        subject=subject,
    )
    
    return VerificationListResponse(
        verifications=verifications,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.get("/stats", response_model=VerificationStats)
async def get_verification_stats(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_verifications"))],
) -> VerificationStats:
    """
    Get verification statistics.
    
    Returns counts of pending, approved, and rejected verifications.
    """
    return await admin_service.get_verification_stats()


@router.get("/{verification_id}", response_model=VerificationResponse)
async def get_verification_details(
    verification_id: UUID,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_verifications"))],
) -> VerificationResponse:
    """
    Get detailed verification information.
    
    Returns complete verification data including documents and tutor profile.
    """
    verification = await admin_service.get_verification_details(verification_id)
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification not found"
        )
    
    return verification


@router.post("/{verification_id}/approve")
async def approve_verification(
    verification_id: UUID,
    action_data: VerificationActionRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("approve_verifications"))],
) -> dict[str, str]:
    """
    Approve tutor verification.
    
    Marks tutor as verified and enables them to create sessions.
    """
    success = await admin_service.approve_verification(
        verification_id=verification_id,
        admin_id=current_admin.id,
        notes=action_data.notes,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification not found or already processed"
        )
    
    return {"message": "Verification approved successfully"}


@router.post("/{verification_id}/reject")
async def reject_verification(
    verification_id: UUID,
    action_data: VerificationActionRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("reject_verifications"))],
) -> dict[str, str]:
    """
    Reject tutor verification.
    
    Rejects verification with reason and allows tutor to resubmit.
    """
    if not action_data.reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reason is required for rejection"
        )
    
    success = await admin_service.reject_verification(
        verification_id=verification_id,
        admin_id=current_admin.id,
        reason=action_data.reason,
        notes=action_data.notes,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification not found or already processed"
        )
    
    return {"message": "Verification rejected"}


@router.get("/tutor/{tutor_id}/history")
async def get_tutor_verification_history(
    tutor_id: UUID,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_verifications"))],
) -> List[VerificationResponse]:
    """
    Get verification history for a specific tutor.
    
    Returns all verification attempts and their outcomes.
    """
    return await admin_service.get_tutor_verification_history(tutor_id)


@router.post("/bulk-approve")
async def bulk_approve_verifications(
    verification_ids: List[UUID],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("approve_verifications"))],
) -> dict[str, int]:
    """
    Bulk approve multiple verifications.
    
    Approves multiple verifications at once for efficiency.
    """
    if len(verification_ids) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve more than 50 verifications at once"
        )
    
    approved_count = await admin_service.bulk_approve_verifications(
        verification_ids=verification_ids,
        admin_id=current_admin.id,
    )
    
    return {
        "message": f"Approved {approved_count} verifications",
        "approved_count": approved_count,
        "total_requested": len(verification_ids),
    }