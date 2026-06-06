from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.repositories.user_repository import UserRepository

# ------------------------------------------------------------------
# FastAPI security scheme – this creates the "Authorize" button in Swagger UI
# ------------------------------------------------------------------
http_bearer = HTTPBearer(auto_error=True)

# ------------------------------------------------------------------
# Dependency that validates a JWT and returns the authenticated User object
# ------------------------------------------------------------------
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        if payload is None:
            raise ValueError("Invalid token")
        sub = payload.get("sub")
        if not sub:
            raise ValueError("missing subject")
        user_id = UUID(str(sub))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from exc

    # First try to look up the user in the local database (synced via Kafka)
    user = await UserRepository(db).get_by_id(user_id)
    if user is not None:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        return user

    # Fallback: accept Admin Service JWT (platform admin is not an Identity user).
    role = payload.get("role", "user")
    email = payload.get("email", "")
    user = User(
        id=user_id,
        email=email,
        role=role,
        is_active=True,
    )
    # Add to session so it can be used within this request context
    db.add(user)
    return user

