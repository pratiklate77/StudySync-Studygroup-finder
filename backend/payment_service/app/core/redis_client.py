from __future__ import annotations

from redis.asyncio import Redis, from_url


async def create_redis(url: str) -> Redis:
    return from_url(url, decode_responses=False)


async def close_redis(redis: Redis) -> None:
    await redis.close()
