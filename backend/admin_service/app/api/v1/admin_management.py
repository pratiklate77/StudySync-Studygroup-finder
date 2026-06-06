from __future__ import annotations

from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_admin_service, get_current_admin, require_permission
from app.models.admin_user import AdminUser
from app.schemas.admin_management import (
    AdminCreateRequest,
    AdminResponse,
    AdminUpdateRequest,
    AdminListResponse,
    PasswordChangeRequest,
)
from app.services.admin_service import AdminService

router = APIRouter()


@router.post("/create", response_model=AdminResponse)
async def create_admin(
    admin_data: AdminCreateRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("create_admin"))],
) -> AdminResponse:
    """
    Create new admin user.
    
    Only super_admin can create other admins.
    """
    # Check if email already exists
    existing_admin = await admin_service.get_admin_by_email(admin_data.email)
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin with this email already exists"
        )
    
    # Only super_admin can create other super_admins
    if admin_data.role == "super_admin" and current_admin.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can create other super admins"
        )
    
    new_admin = await admin_service.create_admin(
        email=admin_data.email,
        password=admin_data.password,
        full_name=admin_data.full_name,
        role=admin_data.role,
        permissions=admin_data.permissions or [],
        created_by=current_admin.id,
    )
    
    return AdminResponse.from_model(new_admin)


@router.get("/list", response_model=AdminListResponse)
async def list_admins(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_admins"))],
    skip: int = 0,
    limit: int = 50,
) -> AdminListResponse:
    """
    List all admin users.
    
    Returns paginated list of admin users.
    """
    admins, total = await admin_service.list_admins(skip=skip, limit=limit)
    
    return AdminListResponse(
        admins=[AdminResponse.from_model(admin) for admin in admins],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{admin_id}", response_model=AdminResponse)
async def get_admin(
    admin_id: UUID,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("view_admins"))],
) -> AdminResponse:
    """
    Get admin user by ID.
    """
    admin = await admin_service.get_admin_by_id(admin_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    return AdminResponse.from_model(admin)


@router.put("/{admin_id}", response_model=AdminResponse)
async def update_admin(
    admin_id: UUID,
    update_data: AdminUpdateRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("update_admin"))],
) -> AdminResponse:
    """
    Update admin user.
    
    Super admin can update anyone, others can only update themselves.
    """
    admin = await admin_service.get_admin_by_id(admin_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    # Permission check
    if current_admin.role != "super_admin" and current_admin.id != admin_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only update your own profile"
        )
    
    # Role change restrictions
    if update_data.role and update_data.role != admin.role:
        if current_admin.role != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admin can change roles"
            )
        
        if admin.role == "super_admin" and current_admin.id != admin_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot change other super admin's role"
            )
    
    updated_admin = await admin_service.update_admin(
        admin_id=admin_id,
        update_data=update_data.model_dump(exclude_unset=True),
        updated_by=current_admin.id,
    )
    
    return AdminResponse.from_model(updated_admin)


@router.post("/{admin_id}/deactivate")
async def deactivate_admin(
    admin_id: UUID,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("deactivate_admin"))],
) -> dict[str, str]:
    """
    Deactivate admin user.
    
    Cannot deactivate yourself or other super admins.
    """
    if current_admin.id == admin_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself"
        )
    
    admin = await admin_service.get_admin_by_id(admin_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    if admin.role == "super_admin" and current_admin.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot deactivate super admin"
        )
    
    await admin_service.deactivate_admin(admin_id, deactivated_by=current_admin.id)
    
    return {"message": "Admin deactivated successfully"}


@router.post("/{admin_id}/activate")
async def activate_admin(
    admin_id: UUID,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("activate_admin"))],
) -> dict[str, str]:
    """
    Activate admin user.
    """
    admin = await admin_service.get_admin_by_id(admin_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    await admin_service.activate_admin(admin_id, activated_by=current_admin.id)
    
    return {"message": "Admin activated successfully"}


@router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> dict[str, str]:
    """
    Change admin password.
    
    Requires current password verification.
    """
    success = await admin_service.change_password(
        admin_id=current_admin.id,
        current_password=password_data.current_password,
        new_password=password_data.new_password,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    return {"message": "Password changed successfully"}


@router.post("/{admin_id}/reset-password")
async def reset_admin_password(
    admin_id: UUID,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    _: Annotated[None, Depends(require_permission("reset_password"))],
) -> dict[str, str]:
    """
    Reset admin password (super admin only).
    
    Generates new temporary password.
    """
    if current_admin.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can reset passwords"
        )
    
    admin = await admin_service.get_admin_by_id(admin_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    new_password = await admin_service.reset_admin_password(
        admin_id=admin_id,
        reset_by=current_admin.id,
    )
    
    return {
        "message": "Password reset successfully",
        "temporary_password": new_password,
        "note": "Admin must change this password on next login"
    }