from __future__ import annotations

import uuid
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import verify_token
from app.models.admin_user import AdminUser
from app.schemas.admin_management import AdminPermissions
from app.services.admin_service import AdminService

security = HTTPBearer()


async def get_admin_service(request: Request) -> AdminService:
    """Dependency to get admin service instance."""
    return request.app.state.admin_service


async def get_current_admin(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> AdminUser:
    """Dependency to get current authenticated admin."""
    token = credentials.credentials
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    admin_id = payload.get("sub")
    if not admin_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    try:
        admin_uuid = uuid.UUID(admin_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin ID format",
        )
    
    admin_profile = await admin_service.get_admin_profile(admin_uuid)
    if not admin_profile or not admin_profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found or inactive",
        )
    
    # Convert AdminProfile back to AdminUser for compatibility
    admin_user = AdminUser(
        id=admin_profile.id,
        email=admin_profile.email,
        full_name=admin_profile.full_name,
        role=admin_profile.role,
        permissions=admin_profile.permissions,
        is_active=admin_profile.is_active,
        last_login=admin_profile.last_login,
        login_count=admin_profile.login_count,
        created_at=admin_profile.created_at,
        password_hash="",  # Not needed for authenticated user
    )
    
    return admin_user


def require_permission(permission: str) -> Callable:
    """Dependency factory to require specific permission."""
    def permission_checker(
        current_admin: Annotated[AdminUser, Depends(get_current_admin)]
    ) -> None:
        # Super admin has all permissions
        if current_admin.role == "super_admin":
            return
        
        # Get role-based permissions
        role_permissions = AdminPermissions.get_role_permissions(current_admin.role)
        
        # Check custom permissions
        admin_permissions = current_admin.permissions or []
        all_permissions = set(role_permissions + admin_permissions)
        
        if permission not in all_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
    
    return permission_checker


def require_super_admin(
    current_admin: Annotated[AdminUser, Depends(get_current_admin)]
) -> AdminUser:
    """Dependency to require super admin role."""
    if current_admin.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return current_admin