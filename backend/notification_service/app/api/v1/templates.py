from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.notification import NotificationTemplate
from pydantic import BaseModel

router = APIRouter()

class TemplateRead(BaseModel):
    id: UUID
    event_type: str
    title_template: str
    message_template: str
    is_active: bool

    class Config:
        from_attributes = True

@router.get("", response_model=list[TemplateRead])
async def list_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotificationTemplate))
    return result.scalars().all()

@router.post("", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(data: dict, db: AsyncSession = Depends(get_db)):
    template = NotificationTemplate(**data)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template

@router.get("/{event_type}", response_model=TemplateRead)
async def get_template(event_type: str, db: AsyncSession = Depends(get_db)):
    stmt = select(NotificationTemplate).where(NotificationTemplate.event_type == event_type)
    template = await db.scalar(stmt)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template