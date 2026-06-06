from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, Depends

from app.schemas.verification import (
    DocumentResponse,
    DocumentUploadRequest,
    VerificationHistoryResponse,
    VerificationRequestResponse,
    VerificationRequestSubmit,
    VerificationStatusResponse,
)
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# ------------------------------------------------------------------
# Helper to extract the authenticated user's UUID
# ------------------------------------------------------------------
def _user_id(user = Depends(get_current_user)) -> uuid.UUID:
    return user.id




@router.get(
    "/status",
    response_model=VerificationStatusResponse,
)
async def get_verification_status(
    request: Request,
    user_id: uuid.UUID = Depends(_user_id),
) -> VerificationStatusResponse:
    """Get the latest verification status for the current user."""
    service = request.app.state.verification_service
    result = await service.get_verification_status(user_id=user_id)
    if not result:
        raise HTTPException(status_code=404, detail="No verification request found")
    return result


@router.get(
    "/history",
    response_model=VerificationHistoryResponse,
)
async def get_verification_history(
    request: Request,
    user_id: uuid.UUID = Depends(_user_id),
) -> VerificationHistoryResponse:
    """Get all past verification requests for the current user."""
    service = request.app.state.verification_service
    return await service.get_verification_history(user_id=user_id)


