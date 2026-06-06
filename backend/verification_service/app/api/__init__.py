from fastapi import APIRouter

from app.api.v1 import verification, admin

api_router = APIRouter()
api_router.include_router(verification.router, prefix="/verification", tags=["verification"])
api_router.include_router(admin.router, prefix="/admin/verification", tags=["admin"])

__all__ = ["api_router"]
