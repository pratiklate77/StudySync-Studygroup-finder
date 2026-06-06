from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_admin_service, get_current_admin
from app.models.admin_user import AdminUser
from app.schemas.auth import AdminLoginRequest, AdminLoginResponse, AdminProfile
from app.services.admin_service import AdminService

router = APIRouter()


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(
    login_data: AdminLoginRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> AdminLoginResponse:
    """
    Admin login endpoint.
    
    Authenticates admin user and returns access token.
    """
    result = await admin_service.authenticate_admin(
        email=login_data.email,
        password=login_data.password,
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    return result


@router.get("/profile", response_model=AdminProfile)
async def get_admin_profile(
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> AdminProfile:
    """
    Get current admin profile.
    
    Returns detailed information about the authenticated admin.
    """
    return AdminProfile(
        id=current_admin.id,
        email=current_admin.email,
        full_name=current_admin.full_name,
        role=current_admin.role,
        permissions=current_admin.permissions,
        is_active=current_admin.is_active,
        last_login=current_admin.last_login,
        login_count=current_admin.login_count,
        created_at=current_admin.created_at,
    )


@router.post("/logout")
async def admin_logout(
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> dict[str, str]:
    """
    Admin logout endpoint.
    
    In a stateless JWT system, logout is handled client-side by discarding the token.
    This endpoint is provided for consistency and potential future token blacklisting.
    """
    return {"message": "Successfully logged out"}