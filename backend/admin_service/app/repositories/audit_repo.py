from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select

from app.core.database import DatabaseManager
from app.models.admin_action import AdminAction

logger = logging.getLogger(__name__)


class AuditRepository:
    """Repository for AdminAction audit trail (Admin DB)."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def log_action(
        self,
        admin_id: uuid.UUID,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
        reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AdminAction:
        """Create and persist an admin action audit record."""
        async with self.db_manager.AdminSessionLocal() as session:
            admin_action = AdminAction(
                admin_id=admin_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details or {},
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(admin_action)
            await session.commit()
            await session.refresh(admin_action)
            return admin_action

    async def get_audit_trail(
        self,
        admin_id: uuid.UUID | None = None,
        action_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch recent audit trail entries."""
        async with self.db_manager.AdminSessionLocal() as session:
            query = select(AdminAction).order_by(AdminAction.created_at.desc()).limit(limit)
            if admin_id:
                query = query.where(AdminAction.admin_id == admin_id)
            if action_type:
                query = query.where(AdminAction.action == action_type)
            result = await session.execute(query)
            actions = result.scalars().all()

        return [
            {
                "id": str(a.id),
                "admin_id": str(a.admin_id),
                "action": a.action,
                "target_type": a.target_type,
                "target_id": a.target_id,
                "created_at": a.created_at.isoformat(),
            }
            for a in actions
        ]