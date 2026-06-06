from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_admin_service, get_current_admin, require_permission
from app.models.admin_user import AdminUser
from app.schemas.user import UserActionRequest, UserListResponse, UserSummary
from app.services.admin_service import AdminService

router = APIRouter()


@router.get("/users", response_model=UserListResponse)
async def get_users(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    _: Annotated[None, Depends(require_permission("view_users"))],
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    role: str | None = Query(None, description="Filter by user role"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    search: str | None = Query(None, description="Search in name/email"),
) -> UserListResponse:
    """
    Get paginated list of users.
    
    Supports filtering by role, active status, and text search.
    """
    users, total = await admin_service.get_users_list(
        page=page,
        per_page=per_page,
        role=role,
        is_active=is_active,
        search=search,
    )
    
    total_pages = (total + per_page - 1) // per_page
    
    return UserListResponse(
        users=users,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: uuid.UUID,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    _: Annotated[None, Depends(require_permission("view_users"))],
):
    """
    Get detailed information about a specific user.
    
    Returns comprehensive user data including profile information.
    """
    user = await admin_service.get_user_details(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in Identity Service",
        )
    
    return user


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: uuid.UUID,
    action_data: UserActionRequest,
    request: Request,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("suspend_users"))],
) -> dict[str, str]:
    success = await admin_service.suspend_user(
        user_id=user_id,
        admin_id=current_admin.id,
        reason=action_data.reason,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return {"message": f"User {user_id} has been suspended"}


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: uuid.UUID,
    action_data: UserActionRequest,
    request: Request,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("activate_users"))],
) -> dict[str, str]:
    success = await admin_service.activate_user(
        user_id=user_id,
        admin_id=current_admin.id,
        reason=action_data.reason,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return {"message": f"User {user_id} has been activated"}


@router.get("/tutors", response_model=UserListResponse)
async def get_tutors(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    _: Annotated[None, Depends(require_permission("view_users"))],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    is_verified: bool | None = Query(None, description="Filter by verification status"),
    search: str | None = Query(None, description="Search in name/email"),
) -> UserListResponse:
    """
    Get paginated list of tutors.
    
    Includes tutor-specific information like verification status and subjects.
    """
    users, total = await admin_service.get_users_list(
        page=page,
        per_page=per_page,
        role="tutor",
        search=search,
    )
    
    total_pages = (total + per_page - 1) // per_page
    
    return UserListResponse(
        users=users,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get("/students", response_model=UserListResponse)
async def get_students(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    _: Annotated[None, Depends(require_permission("view_users"))],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="Search in name/email"),
) -> UserListResponse:
    """
    Get paginated list of students.
    """
    users, total = await admin_service.get_users_list(
        page=page,
        per_page=per_page,
        role="student",
        search=search,
    )
    
    total_pages = (total + per_page - 1) // per_page
    
    return UserListResponse(
        users=users,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.post("/tutors/{user_id}/verify")
async def verify_tutor(
    user_id: uuid.UUID,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("approve_verifications"))],
) -> dict[str, str]:
    """Verify a tutor in Identity and broadcast TUTOR_VERIFIED (Admin Service auth only)."""
    success = await admin_service.verify_platform_tutor(
        user_id=user_id,
        admin_id=current_admin.id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tutor profile not found for this user",
        )
    return {"message": "Tutor verified successfully"}