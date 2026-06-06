from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.auth_middleware import JWTAuthMiddleware
from app.core.config import get_settings
from app.core.database import db_manager, init_models, init_db
from app.core.redis_client import create_redis, close_redis
from app.events.kafka_consumer import UserEventsConsumer
from app.events.kafka_producer import VerificationKafkaProducer
from app.events.verification_events_consumer import VerificationEventsConsumer
from app.kafka.producer import ResilientKafkaProducer
from app.services.verification_service import VerificationService
from app.services.admin_verification_service import AdminVerificationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verification-service")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings

    logger.info("Verification Service starting up...")

    await init_db(settings)
    await init_models()
    logger.info("Database initialized")

    redis = await create_redis(settings.redis_url)
    await redis.ping()
    app.state.redis = redis
    logger.info("Redis connection established")

    # Kafka producer
    kafka_producer_raw = ResilientKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    connected = await kafka_producer_raw.start()
    if not connected:
        logger.warning("Kafka producer not available on startup, will operate in fallback mode")
    app.state.kafka_producer_raw = kafka_producer_raw

    verification_kafka_producer = VerificationKafkaProducer(
        aiokafka_producer=kafka_producer_raw.producer if connected else None
    )
    app.state.kafka_producer = verification_kafka_producer

    # Kafka consumer — USER_EVENTS
    user_consumer = UserEventsConsumer(settings)
    consumer_ok = await user_consumer.start()
    if not consumer_ok:
        logger.warning("UserEventsConsumer not available, continuing without it")
    app.state.user_consumer = user_consumer

    # Kafka consumer — VERIFICATION_EVENTS (consumes TUTOR_APPLICATION_SUBMITTED from identity service)
    verification_events_consumer = VerificationEventsConsumer(settings, db_manager.SessionLocal)
    ve_consumer_ok = await verification_events_consumer.start()
    if not ve_consumer_ok:
        logger.warning("VerificationEventsConsumer not available, continuing without it")
    app.state.verification_events_consumer = verification_events_consumer

    # Services
    app.state.verification_service = VerificationService(
        redis=redis,
        kafka_producer=verification_kafka_producer,
        settings=settings,
    )
    app.state.admin_verification_service = AdminVerificationService(
        redis=redis,
        kafka_producer=verification_kafka_producer,
        settings=settings,
    )

    logger.info("Verification Service startup complete")
    yield

    logger.info("Verification Service shutting down...")
    await user_consumer.stop()
    await verification_events_consumer.stop()
    await kafka_producer_raw.stop()
    await close_redis(redis)
    await db_manager.close_all_connections()
    logger.info("Verification Service shutdown complete")


def create_app() -> FastAPI:
    application = FastAPI(
        title="StudySync Verification Service",
        version="1.0.0",
        description="Handles document verification and KYC for tutors",
        lifespan=lifespan,
    )

    # JWT auth middleware — runs on every request except public paths
    application.add_middleware(JWTAuthMiddleware)

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

    @application.get("/health/kafka", tags=["ops"])
    async def kafka_health() -> dict:
        producer: ResilientKafkaProducer = application.state.kafka_producer_raw
        return {
            "connected": producer.is_connected,
            "status": "ok" if producer.is_connected else "degraded",
        }

    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
