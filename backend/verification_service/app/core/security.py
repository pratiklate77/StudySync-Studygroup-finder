from __future__ import annotations

from typing import Any

import jwt

from app.core.config import get_settings


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate JWT token. Returns payload or None if invalid."""
    try:
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.PyJWTError:
        return None
