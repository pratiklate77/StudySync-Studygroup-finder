from fastapi import APIRouter

from app.api.v1 import analytics, auth, users, admin_management, verification, moderation, system

api_router = APIRouter()

# Authentication routes
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# User management routes  
api_router.include_router(users.router, prefix="/admin", tags=["user-management"])

# Admin management routes
api_router.include_router(admin_management.router, prefix="/admin-management", tags=["admin-management"])

# Verification management routes
api_router.include_router(verification.router, prefix="/verification", tags=["verification"])

# Content moderation routes
api_router.include_router(moderation.router, prefix="/moderation", tags=["moderation"])

# System management routes
api_router.include_router(system.router, prefix="/system", tags=["system"])

# Analytics routes
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])