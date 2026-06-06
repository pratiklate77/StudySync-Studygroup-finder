from typing import Any

import jwt

from app.core.config import get_settings


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT issued by the Identity Service.

    This service NEVER issues tokens — it only validates them using the
    shared secret. Raises jwt.PyJWTError on invalid/expired tokens.
    """
    settings = get_settings()
    print(get_settings.cache_info())
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
