from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)
http_bearer = HTTPBearer(auto_error=True)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> UUID:
    token = credentials.credentials

    try:
        return UUID(token)
    except ValueError as exc:
        logger.debug("Invalid user id token", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user_id token",
        )


async def get_recommendation_service(
    request: Request,
) -> AsyncIterator[RecommendationService]:
    settings = get_settings()

    async with AsyncSessionLocal() as session:
        service = RecommendationService(
            db=session,
            redis=request.app.state.redis,
            settings=settings,
        )
        yield service
