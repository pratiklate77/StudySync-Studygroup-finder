from __future__ import annotations

import redis.asyncio as redis
from redis.asyncio import Redis

from app.core.config import get_settings


async def create_redis(redis_url: str) -> Redis:
    """Create Redis connection."""
    return redis.from_url(redis_url, decode_responses=True)


async def close_redis(redis_client: Redis) -> None:
    """Close Redis connection."""
    await redis_client.aclose()


async def get_redis() -> Redis:
    """Dependency for Redis client."""
    settings = get_settings()
    redis_client = await create_redis(settings.redis_url)
    try:
        yield redis_client
    finally:
        await close_redis(redis_client)