from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user_id, get_notification_service
from app.schemas.notification import NotificationListResponse, UnreadCountResponse

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    current_user_id: UUID = Depends(get_current_user_id),
    page: int = 1,
    per_page: int = 20,
    unread_only: bool = False,
    notification_type: str | None = None,
    service = Depends(get_notification_service),
) -> NotificationListResponse:
    return await service.list_notifications(
        user_id=current_user_id,
        page=page,
        per_page=per_page,
        unread_only=unread_only,
        notification_type=notification_type,
    )


@router.get("/unread", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user_id: UUID = Depends(get_current_user_id),
    service = Depends(get_notification_service),
) -> UnreadCountResponse:
    return await service.get_unread_count(current_user_id)


@router.patch("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(
    notification_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    service = Depends(get_notification_service),
) -> None:
    updated = await service.mark_read(notification_id, current_user_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")


@router.patch("/read", response_model=dict[str, int])
async def mark_all_notifications_read(
    current_user_id: UUID = Depends(get_current_user_id),
    service = Depends(get_notification_service),
) -> dict[str, int]:
    updated_count = await service.mark_all_read(current_user_id)
    return {"updated_count": updated_count}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    service = Depends(get_notification_service),
) -> None:
    deleted = await service.delete_notification(notification_id, current_user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
