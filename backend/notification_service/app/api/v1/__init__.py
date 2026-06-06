from fastapi import APIRouter

from app.api.v1 import notifications, preferences, templates, websocket

api_router = APIRouter()
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(preferences.router, prefix="/preferences", tags=["preferences"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(websocket.router, tags=["websocket"])
