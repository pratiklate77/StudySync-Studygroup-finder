from redis.asyncio import Redis


async def create_redis(redis_url: str) -> Redis:
    """Create and return Redis client."""
    return await Redis.from_url(redis_url, decode_responses=True)


async def close_redis(redis: Redis) -> None:
    """Close Redis connection."""
    await redis.close()
