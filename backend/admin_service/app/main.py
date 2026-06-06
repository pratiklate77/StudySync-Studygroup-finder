import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.database import db_manager
from app.core.redis_client import create_redis, close_redis
from app.core.security_middleware import SecurityMiddleware
from app.kafka.circuit_breaker import CircuitBreaker
from app.kafka.fallback_store import InMemoryFallbackStore
from app.kafka.producer import AdminKafkaProducer
from app.kafka.retry_worker import AdminKafkaRetryWorker
from app.services.admin_service import AdminService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("admin-service")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Admin Service Lifespan Manager: Handles startup and shutdown.
    
    Manages connections to:
    - Admin service database
    - Redis cache
    - Kafka for admin event broadcasting
    """
    # === STARTUP PHASE ===
    logger.info("Starting Admin Service...")
    
    # Load configuration
    settings = get_settings()
    app.state.settings = settings
    
    # Connect to Redis
    logger.info("Connecting to Redis...")
    redis = await create_redis(settings.redis_url)
    await redis.ping()
    app.state.redis = redis
    logger.info("Redis connection established")
    
    # Set up Kafka components
    logger.info("Setting up Kafka components...")
    
    fallback_store = InMemoryFallbackStore()
    circuit_breaker = CircuitBreaker(
        failure_threshold=settings.kafka_circuit_breaker_failure_threshold,
        recovery_timeout=settings.kafka_circuit_breaker_recovery_timeout_seconds,
    )
    
    # Kafka producer for admin events
    kafka_producer = AdminKafkaProducer(
        settings=settings,
        circuit_breaker=circuit_breaker,
        fallback_store=fallback_store,
    )
    
    # Try to connect to Kafka (non-blocking)
    try:
        connected = await kafka_producer.start()
        if not connected:
            logger.warning("Continuing startup with Kafka in fallback mode")
        else:
            logger.info("Admin Kafka producer connected")
    except Exception as e:
        logger.warning(f"Kafka connection failed: {e}. Continuing in fallback mode.")
        connected = False
    
    # Retry worker for failed events
    retry_worker = AdminKafkaRetryWorker(
        producer=kafka_producer,
        fallback_store=fallback_store,
        base_delay=settings.kafka_retry_base_delay_seconds,
        max_delay=settings.kafka_retry_max_delay_seconds,
    )
    
    retry_task = asyncio.create_task(
        retry_worker.run(), 
        name="admin-kafka-retry-worker"
    )
    
    # Store components in app state
    app.state.kafka_producer = kafka_producer
    app.state.kafka_retry_worker = retry_worker
    app.state.kafka_retry_task = retry_task
    
    # Initialize admin service
    admin_service = AdminService(
        db_manager=db_manager,
        redis=redis,
        kafka_producer=kafka_producer,
        settings=settings,
    )
    app.state.admin_service = admin_service
    
    # Create super admin if not exists
    await admin_service.ensure_super_admin()
    
    logger.info("Admin service startup complete")
    
    # === YIELD CONTROL TO APPLICATION ===
    yield
    
    # === SHUTDOWN PHASE ===
    logger.info("Shutting down Admin Service...")
    
    # Stop retry worker
    await retry_worker.stop()
    await retry_task
    logger.info("Admin Kafka retry worker stopped")
    
    # Stop Kafka producer
    await kafka_producer.stop()
    logger.info("Admin Kafka producer stopped")
    
    # Close Redis connection
    await close_redis(redis)
    logger.info("Redis connection closed")
    
    # Close all database connections
    await db_manager.close_all_connections()
    logger.info("All database connections closed")
    
    logger.info("Admin service shutdown complete")


def create_app() -> FastAPI:
    """
    Admin Service Application Factory.
    
    Creates FastAPI application with:
    - Security middleware for rate limiting
    - Health check endpoints
    - Admin API routes
    - Kafka health monitoring
    """
    application = FastAPI(
        title="StudySync Admin Service",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # Add security middleware
    application.add_middleware(SecurityMiddleware)
    
    # Add CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health Check Endpoints
    @application.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        """Basic health check."""
        return {"status": "ok"}

    @application.get("/health/kafka", tags=["ops"])
    async def kafka_health(request: Request) -> dict:
        """Kafka health check with detailed status."""
        producer: AdminKafkaProducer = request.app.state.kafka_producer
        state = await producer._circuit_breaker.current_state()
        
        return {
            "circuit_breaker": state.value,
            "fallback_queue_size": await producer.fallback_queue_size(),
        }

    @application.get("/health/dependencies", tags=["ops"])
    async def dependency_health(request: Request) -> dict:
        """Check health of dependent services via Internal APIs."""
        import httpx
        settings = request.app.state.settings
        results = {}
        
        try:
            # 1. Check own DB
            async with db_manager.AdminSessionLocal() as session:
                from sqlalchemy import text
                await session.execute(text("SELECT 1"))
            results["admin_db"] = "ok"
            
            # 2. Check dependent services (Internal APIs)
            async with httpx.AsyncClient(timeout=2.0) as client:
                # We query the health of the service, not its DB directly
                resp = await client.get(f"{settings.identity_service_url}/health")
                results["identity_service"] = "ok" if resp.status_code == 200 else "degraded"
                
                resp = await client.get(f"{settings.group_service_url}/health")
                results["group_service"] = "ok" if resp.status_code == 200 else "degraded"

            return results
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "error", "message": str(e)}

    # Include API routes
    application.include_router(api_router, prefix="/api/v1")
    
    return application


# Create the application instance
app = create_app()