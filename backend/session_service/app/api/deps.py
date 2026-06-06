from uuid import UUID
import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import httpx

from app.core.security import decode_access_token
from app.core.config import get_settings

logger = logging.getLogger(__name__)

http_bearer = HTTPBearer(auto_error=True)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> UUID:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject (sub)")
        try:
            return UUID(sub)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user_id format")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("JWT validation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def get_user_email(user_id: UUID, token: str) -> str | None:
    """Fetch user email from identity service using the bearer token."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{settings.identity_service_url}/api/v1/auth/users/{user_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                return resp.json().get("email")
    except Exception as exc:
        logger.warning("Could not fetch user email for %s: %s", user_id, exc)
    return None