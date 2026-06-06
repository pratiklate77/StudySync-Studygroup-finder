import httpx
import logging
from uuid import UUID
from app.core.config import Settings

logger = logging.getLogger(__name__)

class IdentityInternalClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.identity_service_url
        self.timeout = 5.0

    async def suspend_user(self, user_id: UUID, reason: str) -> bool:
        """
        Calls the Identity Service's internal API to suspend a user.
        This is much safer than direct DB updates.
        """
        url = f"{self.base_url}/api/v1/internal/users/{user_id}/suspend"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json={"reason": reason})
                if response.status_code == 200:
                    logger.info(f"User {user_id} suspended via Identity API")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to communicate with Identity Service: {e}")
            return False