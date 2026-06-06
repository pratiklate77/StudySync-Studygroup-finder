from __future__ import annotations

from uuid import UUID

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.security import decode_token

# Paths that don't require authentication
_PUBLIC_PATHS = {"/health", "/health/kafka", "/docs", "/openapi.json", "/redoc"}


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Decodes JWT from Authorization header and sets request.state.user_id and user_role."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid Authorization header"})

        token = auth_header[len("Bearer "):]
        payload = decode_token(token)
        if not payload:
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})

        try:
            request.state.user_id = UUID(str(payload["sub"]))
        except (KeyError, ValueError):
            return JSONResponse(status_code=401, content={"detail": "Invalid token payload"})

        request.state.user_role = payload.get("role", "user")
        return await call_next(request)
