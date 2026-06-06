import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from aiokafka import AIOKafkaProducer

from app.api import api_router
from app.core.config import get_settings
from app.core.database import db_manager, init_models
from app.core.redis_client import create_redis, close_redis
from app.services.payment_service import PaymentService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("payment-service")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings

    # Initialize database schema if necessary
    await init_models()

    redis = await create_redis(settings.redis_url)
    await redis.ping()
    app.state.redis = redis
    logger.info("Redis connection established")

    # Kafka producer (non-blocking startup with bounded retries)
    kafka_producer = None
    for attempt in range(1, settings.kafka_startup_max_retries + 1):
        try:
            kafka_producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
                acks="all",
                enable_idempotence=True,
                compression_type="gzip",
                linger_ms=10,
                request_timeout_ms=int(settings.kafka_send_timeout_seconds * 1000),
            )
            await asyncio.wait_for(
                kafka_producer.start(),
                timeout=settings.kafka_startup_timeout_seconds,
            )
            logger.info("Kafka producer connected on attempt %d", attempt)
            break
        except Exception as e:
            logger.warning(
                "Kafka startup attempt %d/%d failed: %s",
                attempt,
                settings.kafka_startup_max_retries,
                e,
            )
            kafka_producer = None
            if attempt < settings.kafka_startup_max_retries:
                await asyncio.sleep(settings.kafka_startup_retry_delay_seconds)
    if kafka_producer is None:
        logger.warning("Kafka unavailable after retries. Payment events will not be published.")
    app.state.kafka_producer = kafka_producer

    app.state.payment_service = PaymentService(
        db_manager=db_manager,
        redis=redis,
        settings=settings,
        kafka_producer=kafka_producer,
    )

    logger.info("Payment service startup complete")
    yield

    await close_redis(redis)
    if kafka_producer:
        await kafka_producer.stop()
    logger.info("Redis connection closed")
    await db_manager.close_all_connections()
    logger.info("Payment service shutdown complete")


def create_app() -> FastAPI:
    application = FastAPI(
        title="StudySync Payment Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    @application.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
