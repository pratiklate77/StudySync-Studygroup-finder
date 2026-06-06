import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.redis_client import close_redis, create_redis
from app.events.kafka_consumer import RatingEventsConsumer
from app.events.user_events_consumer import UserEventsConsumer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recommendation-service")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    redis = await create_redis(settings.redis_url)
    await redis.ping()
    app.state.redis = redis

    consumer = RatingEventsConsumer(settings, AsyncSessionLocal, redis)
    consumer_connected = await consumer.start()
    if not consumer_connected:
        logger.warning("Continuing startup without rating events consumer")
    app.state.rating_consumer = consumer

    # User events consumer — reacts to TUTOR_VERIFIED/TUTOR_REJECTED from USER_EVENTS
    user_consumer = UserEventsConsumer(settings, AsyncSessionLocal)
    user_consumer_connected = await user_consumer.start()
    if not user_consumer_connected:
        logger.warning("Continuing startup without user events consumer")
    app.state.user_consumer = user_consumer

    logger.info("Recommendation service startup complete")
    yield
    await user_consumer.stop()
    await consumer.stop()
    await close_redis(redis)
    logger.info("Recommendation service shutdown complete")


def create_app() -> FastAPI:
    application = FastAPI(
        title="StudySync Recommendation Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    @application.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
