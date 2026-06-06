from __future__ import annotations

from typing import Any
from uuid import UUID

import jwt

from app.core.config import get_settings


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        settings = get_settings()
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
