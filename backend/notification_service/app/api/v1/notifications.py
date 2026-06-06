from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user_id, get_notification_service
from app.schemas.notification import NotificationListResponse, NotificationRead, UnreadCountResponse, NewCountResponse

router = APIRouter()


@router.get("", response_model=list[NotificationRead])
@router.get("/", response_model=list[NotificationRead], include_in_schema=False)
async def list_notifications(
    current_user_id: UUID = Depends(get_current_user_id),
    page: int = 1,
    per_page: int = 20,
    unread_only: bool = False,
    notification_type: str | None = None,
    service = Depends(get_notification_service),
) -> list[NotificationRead]:
    result = await service.list_notifications(
        user_id=current_user_id,
        page=page,
        per_page=per_page,
        unread_only=unread_only,
        notification_type=notification_type,
    )
    return result.items


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user_id: UUID = Depends(get_current_user_id),
    service = Depends(get_notification_service),
) -> UnreadCountResponse:
    return await service.get_unread_count(current_user_id)


@router.get("/new-count", response_model=NewCountResponse)
async def get_new_count(
    current_user_id: UUID = Depends(get_current_user_id),
    service = Depends(get_notification_service),
) -> NewCountResponse:
    return await service.get_new_count(current_user_id)


@router.post("/seen-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_seen(
    current_user_id: UUID = Depends(get_current_user_id),
    service = Depends(get_notification_service),
) -> None:
    await service.mark_all_seen(current_user_id)


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(
    notification_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    service = Depends(get_notification_service),
) -> None:
    updated = await service.mark_read(notification_id, current_user_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")


@router.post("/read-all", response_model=dict[str, int])
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
