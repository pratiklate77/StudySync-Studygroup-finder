from __future__ import annotations

import logging
import uuid
from typing import Any

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.kafka.producer import AdminKafkaProducer
from app.models.admin_user import AdminUser
from app.repositories.admin_repo import AdminRepository
from app.repositories.analytics_repo import AnalyticsRepository
from app.repositories.audit_repo import AuditRepository
from app.repositories.user_repo import UserRepository
from app.schemas.analytics import DashboardOverview
from app.schemas.auth import AdminLoginResponse, AdminProfile
from app.schemas.moderation import ChatModerationResponse, ModerationStats
from app.schemas.system import (
    PlatformSettingsResponse,
    ServiceStatusResponse,
    SystemHealthResponse,
    SystemStatsResponse,
)
from app.schemas.user import UserSummary
from app.schemas.verification import VerificationStats
from app.services.admin_management_service import AdminManagementService
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import AuthService
from app.services.moderation_service import ModerationService
from app.services.system_service import SystemService
from app.services.tutor_service import TutorService
from app.services.user_management_service import UserManagementService
from app.services.verification_service import VerificationService

logger = logging.getLogger(__name__)


class AdminService:
    """
    Core admin service facade.
    
    Delegates all operations to domain-specific services.
    This class provides backward compatibility for all existing API routes
    that depend on `AdminService`.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        redis: Redis,
        kafka_producer: AdminKafkaProducer,
        settings: Settings,
    ):
        # Initialize repos
        self.admin_repo = AdminRepository(db_manager)
        self.user_repo = UserRepository(db_manager)
        self.analytics_repo = AnalyticsRepository(db_manager)
        self.audit_repo = AuditRepository(db_manager)

        # Initialize domain services
        self.auth_service = AuthService(
            admin_repo=self.admin_repo,
            audit_repo=self.audit_repo,
            kafka_producer=kafka_producer,
            settings=settings,
        )
        self.user_management_service = UserManagementService(
            user_repo=self.user_repo,
            audit_repo=self.audit_repo,
            kafka_producer=kafka_producer,
        )
        self.tutor_service = TutorService(
            user_repo=self.user_repo,
            audit_repo=self.audit_repo,
            kafka_producer=kafka_producer,
        )
        self.admin_management_service = AdminManagementService(
            admin_repo=self.admin_repo,
            audit_repo=self.audit_repo,
        )
        self.analytics_service = AnalyticsService(
            user_repo=self.user_repo,
            analytics_repo=self.analytics_repo,
            audit_repo=self.audit_repo,
            redis=redis,
            kafka_producer=kafka_producer,
            settings=settings,
        )
        self.system_service = SystemService(
            audit_repo=self.audit_repo,
            redis=redis,
            kafka_producer=kafka_producer,
        )
        self.verification_service = VerificationService()
        self.moderation_service = ModerationService()

        # Keep references for direct access
        self.redis = redis
        self.kafka_producer = kafka_producer
        self.settings = settings

    # ── Auth ────────────────────────────────────────────────────────────

    async def ensure_super_admin(self) -> None:
        await self.auth_service.ensure_super_admin()

    async def authenticate_admin(self, email: str, password: str) -> AdminLoginResponse | None:
        return await self.auth_service.authenticate_admin(email, password)

    async def get_admin_profile(self, admin_id: uuid.UUID) -> AdminProfile | None:
        return await self.auth_service.get_admin_profile(admin_id)

    async def log_admin_action(
        self,
        admin_id: uuid.UUID,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
        reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        await self.auth_service.log_admin_action(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # ── User Management ─────────────────────────────────────────────────

    async def get_users_list(
        self,
        page: int = 1,
        per_page: int = 20,
        role: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[UserSummary], int]:
        return await self.user_management_service.get_users_list(
            page=page,
            per_page=per_page,
            role=role,
            is_active=is_active,
            search=search,
        )

    async def get_user_details(self, user_id: uuid.UUID) -> dict | None:
        return await self.user_management_service.get_user_details(user_id)

    async def suspend_user(
        self, user_id: uuid.UUID, admin_id: uuid.UUID, reason: str | None = None
    ) -> bool:
        return await self.user_management_service.suspend_user(
            user_id=user_id, admin_id=admin_id, reason=reason
        )

    async def activate_user(
        self, user_id: uuid.UUID, admin_id: uuid.UUID, reason: str | None = None
    ) -> bool:
        return await self.user_management_service.activate_user(
            user_id=user_id, admin_id=admin_id, reason=reason
        )

    # ── Tutor ───────────────────────────────────────────────────────────

    async def verify_platform_tutor(self, user_id: uuid.UUID, admin_id: uuid.UUID) -> bool:
        return await self.tutor_service.verify_platform_tutor(
            user_id=user_id, admin_id=admin_id
        )

    # ── Admin Management ────────────────────────────────────────────────

    async def get_admin_by_email(self, email: str) -> AdminUser | None:
        return await self.admin_management_service.get_admin_by_email(email)

    async def get_admin_by_id(self, admin_id: uuid.UUID) -> AdminUser | None:
        return await self.admin_management_service.get_admin_by_id(admin_id)

    async def create_admin(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str,
        permissions: list[str],
        created_by: uuid.UUID,
    ) -> AdminUser:
        return await self.admin_management_service.create_admin(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
            permissions=permissions,
            created_by=created_by,
        )

    async def list_admins(
        self, skip: int = 0, limit: int = 50
    ) -> tuple[list[AdminUser], int]:
        return await self.admin_management_service.list_admins(skip=skip, limit=limit)

    async def update_admin(
        self,
        admin_id: uuid.UUID,
        update_data: dict[str, Any],
        updated_by: uuid.UUID,
    ) -> AdminUser:
        return await self.admin_management_service.update_admin(
            admin_id=admin_id, update_data=update_data, updated_by=updated_by
        )

    async def deactivate_admin(self, admin_id: uuid.UUID, deactivated_by: uuid.UUID) -> None:
        await self.admin_management_service.deactivate_admin(
            admin_id=admin_id, deactivated_by=deactivated_by
        )

    async def activate_admin(self, admin_id: uuid.UUID, activated_by: uuid.UUID) -> None:
        await self.admin_management_service.activate_admin(
            admin_id=admin_id, activated_by=activated_by
        )

    async def change_password(
        self, admin_id: uuid.UUID, current_password: str, new_password: str
    ) -> bool:
        return await self.admin_management_service.change_password(
            admin_id=admin_id,
            current_password=current_password,
            new_password=new_password,
        )

    async def reset_admin_password(
        self, admin_id: uuid.UUID, reset_by: uuid.UUID
    ) -> str:
        return await self.admin_management_service.reset_admin_password(
            admin_id=admin_id, reset_by=reset_by
        )

    # ── Analytics ───────────────────────────────────────────────────────

    async def get_dashboard_overview(self) -> DashboardOverview:
        return await self.analytics_service.get_dashboard_overview()

    # Backward-compatible metric helpers
    async def _get_total_users(self) -> int:
        return await self.user_repo.count_total_users()

    async def _get_total_tutors(self) -> int:
        return await self.user_repo.count_total_tutors()

    async def _get_total_students(self) -> int:
        return await self.user_repo.count_total_students()

    async def _get_active_users_today(self) -> int:
        return await self.user_repo.count_active_users_today()

    async def _get_total_sessions(self) -> int:
        return await self.analytics_repo.count_total_sessions()

    async def _get_completed_sessions(self) -> int:
        return await self.analytics_repo.count_completed_sessions()

    async def _get_total_groups(self) -> int:
        return await self.analytics_repo.count_total_groups()

    # ── System ──────────────────────────────────────────────────────────

    async def get_platform_settings(self) -> PlatformSettingsResponse:
        return await self.system_service.get_platform_settings()

    async def update_platform_settings(
        self, settings_update, updated_by: uuid.UUID
    ) -> PlatformSettingsResponse:
        return await self.system_service.update_platform_settings(
            settings_update=settings_update, updated_by=updated_by
        )

    async def get_system_health(self) -> SystemHealthResponse:
        return await self.system_service.get_system_health()

    async def get_service_status(self) -> ServiceStatusResponse:
        return await self.system_service.get_service_status()

    async def get_system_stats(self) -> SystemStatsResponse:
        return await self.system_service.get_system_stats()

    async def enable_maintenance_mode(
        self, admin_id: uuid.UUID, message: str, estimated_duration: int | None
    ) -> bool:
        return await self.system_service.enable_maintenance_mode(
            admin_id=admin_id, message=message, estimated_duration=estimated_duration
        )

    async def disable_maintenance_mode(self, admin_id: uuid.UUID) -> bool:
        return await self.system_service.disable_maintenance_mode(admin_id=admin_id)

    async def create_system_backup(
        self,
        admin_id: uuid.UUID,
        backup_type: str,
        include_files: bool,
        description: str | None,
    ) -> uuid.UUID:
        return await self.system_service.create_system_backup(
            admin_id=admin_id,
            backup_type=backup_type,
            include_files=include_files,
            description=description,
        )

    async def list_system_backups(self) -> dict:
        return await self.system_service.list_system_backups()

    async def clear_system_cache(
        self, admin_id: uuid.UUID, cache_type: str | None
    ) -> str:
        return await self.system_service.clear_system_cache(
            admin_id=admin_id, cache_type=cache_type
        )

    async def get_system_logs(
        self, service: str | None, level: str | None, limit: int
    ) -> dict:
        return await self.system_service.get_system_logs(
            service=service, level=level, limit=limit
        )

    async def get_audit_trail(
        self,
        admin_id: uuid.UUID | None = None,
        action_type: str | None = None,
        limit: int = 100,
    ) -> dict:
        return await self.system_service.get_audit_trail(
            admin_id=admin_id, action_type=action_type, limit=limit
        )

    async def broadcast_notification(
        self,
        admin_id: uuid.UUID,
        title: str | None,
        message: str | None,
        target_audience: str,
        priority: str,
    ) -> uuid.UUID:
        return await self.system_service.broadcast_notification(
            admin_id=admin_id,
            title=title,
            message=message,
            target_audience=target_audience,
            priority=priority,
        )

    # ── Verification ────────────────────────────────────────────────────

    async def get_pending_verifications(
        self, page: int, per_page: int, subject: str | None
    ) -> tuple[list, int]:
        return await self.verification_service.get_pending_verifications(
            page=page, per_page=per_page, subject=subject
        )

    async def get_verification_stats(self) -> VerificationStats:
        return await self.verification_service.get_verification_stats()

    async def get_verification_details(self, verification_id: uuid.UUID):
        return await self.verification_service.get_verification_details(verification_id)

    async def approve_verification(
        self,
        verification_id: uuid.UUID,
        admin_id: uuid.UUID,
        notes: str | None,
    ) -> bool:
        return await self.verification_service.approve_verification(
            verification_id=verification_id, admin_id=admin_id, notes=notes
        )

    async def reject_verification(
        self,
        verification_id: uuid.UUID,
        admin_id: uuid.UUID,
        reason: str,
        notes: str | None,
    ) -> bool:
        return await self.verification_service.reject_verification(
            verification_id=verification_id,
            admin_id=admin_id,
            reason=reason,
            notes=notes,
        )

    async def get_tutor_verification_history(self, tutor_id: uuid.UUID) -> list:
        return await self.verification_service.get_tutor_verification_history(tutor_id)

    async def bulk_approve_verifications(
        self, verification_ids: list, admin_id: uuid.UUID
    ) -> int:
        return await self.verification_service.bulk_approve_verifications(
            verification_ids=verification_ids, admin_id=admin_id
        )

    # ── Moderation ──────────────────────────────────────────────────────

    async def get_reports(
        self,
        page: int,
        per_page: int,
        status_filter: str | None,
        report_type: str | None,
    ) -> tuple[list, int]:
        return await self.moderation_service.get_reports(
            page=page,
            per_page=per_page,
            status_filter=status_filter,
            report_type=report_type,
        )

    async def get_moderation_stats(self) -> ModerationStats:
        return await self.moderation_service.get_moderation_stats()

    async def get_report_details(self, report_id: uuid.UUID):
        return await self.moderation_service.get_report_details(report_id)

    async def resolve_report(
        self,
        report_id: uuid.UUID,
        admin_id: uuid.UUID,
        action_taken: str,
        resolution_notes: str | None,
    ) -> bool:
        return await self.moderation_service.resolve_report(
            report_id=report_id,
            admin_id=admin_id,
            action_taken=action_taken,
            resolution_notes=resolution_notes,
        )

    async def dismiss_report(
        self, report_id: uuid.UUID, admin_id: uuid.UUID, reason: str
    ) -> bool:
        return await self.moderation_service.dismiss_report(
            report_id=report_id, admin_id=admin_id, reason=reason
        )

    async def get_flagged_messages(
        self, page: int, per_page: int, severity: str | None
    ) -> ChatModerationResponse:
        return await self.moderation_service.get_flagged_messages(
            page=page, per_page=per_page, severity=severity
        )

    async def delete_chat_message(
        self, message_id: uuid.UUID, admin_id: uuid.UUID, reason: str
    ) -> bool:
        return await self.moderation_service.delete_chat_message(
            message_id=message_id, admin_id=admin_id, reason=reason
        )

    async def warn_user_for_message(
        self, message_id: uuid.UUID, admin_id: uuid.UUID, warning_reason: str
    ) -> bool:
        return await self.moderation_service.warn_user_for_message(
            message_id=message_id,
            admin_id=admin_id,
            warning_reason=warning_reason,
        )

    async def get_reported_sessions(
        self, page: int, per_page: int
    ) -> dict:
        return await self.moderation_service.get_reported_sessions(
            page=page, per_page=per_page
        )

    async def cancel_session(
        self, session_id: uuid.UUID, admin_id: uuid.UUID, reason: str
    ) -> bool:
        return await self.moderation_service.cancel_session(
            session_id=session_id, admin_id=admin_id, reason=reason
        )

    async def bulk_moderate_content(
        self,
        content_ids: list,
        admin_id: uuid.UUID,
        action: str | None,
        reason: str,
    ) -> int:
        return await self.moderation_service.bulk_moderate_content(
            content_ids=content_ids,
            admin_id=admin_id,
            action=action,
            reason=reason,
        )