import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.database import db_manager
from app.core.redis_client import close_redis, create_redis
from app.events.kafka_consumer import NotificationEventConsumer
from app.core.websocket_manager import WebSocketManager
from app.services.email_worker import EmailVerificationWorker

logger = logging.getLogger("notification-service")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings

    redis_client = await create_redis(settings.redis_url)
    app.state.redis = redis_client

    # Initialize Scalable WebSocket Manager
    ws_manager = WebSocketManager(redis_client)
    await ws_manager.start_pubsub_listener()
    app.state.ws_manager = ws_manager

    consumer = NotificationEventConsumer(
        settings=settings,
        session_factory=db_manager.SessionLocal,
        redis=redis_client, ws_manager=ws_manager
    )
    app.state.notification_consumer = consumer

    connected = await consumer.start()
    if not connected:
        logger.warning("Continuing startup without Kafka consumer; events will not be processed")

    email_worker = EmailVerificationWorker(settings=settings)
    app.state.email_worker = email_worker
    email_connected = await email_worker.start()
    if not email_connected:
        logger.warning("Email verification worker unavailable; verification emails will not be sent")

    logger.info("Notification service startup complete")
    yield

    await ws_manager.stop()
    await consumer.stop()
    await email_worker.stop()
    await close_redis(redis_client)
    await db_manager.close()
    logger.info("Notification service shutdown complete")


def create_app() -> FastAPI:
    application = FastAPI(
        title="StudySync Notification Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
