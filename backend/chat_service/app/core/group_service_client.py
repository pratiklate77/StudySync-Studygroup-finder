"""HTTP client for group_service internal APIs.

Used as fallback when local Kafka-synced data is unavailable.
Allows chat_service to verify membership directly from group_service.
"""
from __future__ import annotations

import logging
from uuid import UUID

import httpx

from app.models.group_membership import GroupMembership

logger = logging.getLogger(__name__)


class GroupServiceClient:
    """Calls group_service internal endpoints for membership verification."""

    def __init__(self, base_url: str, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    async def check_membership(self, group_id: UUID, user_id: UUID) -> GroupMembership | None:
        """Query group_service to check if user is a member of the group.

        Returns GroupMembership with is_active=True if member, None otherwise.
        This is a fallback when local Kafka-synced data is unavailable.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/internal/groups/{group_id}/members/{user_id}",
                )
                response.raise_for_status()
                data = response.json()

                if not data.get("is_member"):
                    return None

                # Create GroupMembership object from response
                # The internal API returns {"is_member": True, "role": "admin|member"}
                role_value = data.get("role", "member")
                # Handle case where role might come as dict or object
                if isinstance(role_value, dict):
                    role_value = role_value.get("value", "member") or "member"
                role_str = str(role_value).lower() if role_value else "member"
                
                membership = GroupMembership(
                    group_id=group_id,
                    user_id=user_id,
                    role=role_str,
                    chat_enabled=True,
                    is_active=True,
                )
                logger.debug(
                    "Fallback membership check succeeded: group=%s user=%s role=%s",
                    group_id,
                    user_id,
                    membership.role,
                )
                return membership
        except httpx.TimeoutException:
            logger.warning(
                "Group service timeout during fallback membership check: group=%s user=%s",
                group_id,
                user_id,
            )
            return None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.debug("User not a member in group_service: group=%s user=%s", group_id, user_id)
                return None
            logger.warning(
                "Group service error during fallback membership check (status=%d): group=%s user=%s",
                exc.response.status_code,
                group_id,
                user_id,
            )
            return None
        except httpx.RequestError as exc:
            logger.warning(
                "Group service request failed during fallback membership check: group=%s user=%s error=%s",
                group_id,
                user_id,
                exc,
            )
            return None
        except Exception as exc:
            logger.error(
                "Unexpected error during fallback membership check: group=%s user=%s error=%s",
                group_id,
                user_id,
                exc,
            )
            return None

    async def check_permissions(self, group_id: UUID, user_id: UUID) -> dict | None:
        """Query group_service to check if user can send messages.

        Returns dict with {"can_send_message": bool, "role": str} if successful, None on error.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/internal/groups/{group_id}/permissions/{user_id}",
                )
                response.raise_for_status()
                logger.debug("Fallback permission check succeeded: group=%s user=%s", group_id, user_id)
                return response.json()
        except httpx.TimeoutException:
            logger.warning(
                "Group service timeout during fallback permission check: group=%s user=%s",
                group_id,
                user_id,
            )
            return None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.debug("User not found in group_service: group=%s user=%s", group_id, user_id)
                return None
            logger.warning(
                "Group service error during fallback permission check (status=%d): group=%s user=%s",
                exc.response.status_code,
                group_id,
                user_id,
            )
            return None
        except httpx.RequestError as exc:
            logger.warning(
                "Group service request failed during fallback permission check: group=%s user=%s error=%s",
                group_id,
                user_id,
                exc,
            )
            return None
        except Exception as exc:
            logger.error(
                "Unexpected error during fallback permission check: group=%s user=%s error=%s",
                group_id,
                user_id,
                exc,
            )
            return None
