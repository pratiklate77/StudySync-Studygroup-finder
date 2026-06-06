from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id, get_notification_service
from app.schemas.notification import NotificationPreferenceResponse, NotificationPreferenceUpdate

router = APIRouter()


@router.get("", response_model=NotificationPreferenceResponse)
async def get_preferences(
    current_user_id: UUID = Depends(get_current_user_id),
    service = Depends(get_notification_service),
) -> NotificationPreferenceResponse:
    return await service.get_preferences(current_user_id)


@router.put("", response_model=NotificationPreferenceResponse)
async def update_preferences(
    payload: NotificationPreferenceUpdate,
    current_user_id: UUID = Depends(get_current_user_id),
    service = Depends(get_notification_service),
) -> NotificationPreferenceResponse:
    return await service.update_preferences(current_user_id, payload)
