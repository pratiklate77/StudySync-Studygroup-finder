from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration settings for Verification Service."""
    
    # Service name
    service_name: str = "verification-service"
    
    # Database Configuration
    database_url: str = "postgresql+asyncpg://studysync:studysync_dev@localhost:5446/verification_db"
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl_seconds: int = 3600  # 1 hour
    
    # JWT (shared secret — decode only)
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"

    # Kafka Configuration
    kafka_bootstrap_servers: str = "kafka:29092"
    kafka_client_id: str = "verification-service"
    kafka_verification_events_topic: str = "VERIFICATION_EVENTS"
    kafka_user_events_topic: str = "USER_EVENTS"
    kafka_send_timeout_seconds: float = 5.0
    kafka_startup_timeout_seconds: float = 10.0
    kafka_startup_max_retries: int = 5
    kafka_startup_retry_delay_seconds: float = 3.0
    kafka_consumer_session_timeout_ms: int = 30000
    kafka_consumer_heartbeat_interval_ms: int = 10000
    kafka_consumer_request_timeout_ms: int = 40000
    kafka_consumer_retry_backoff_ms: int = 1000
    kafka_circuit_breaker_failure_threshold: int = 3
    kafka_circuit_breaker_recovery_timeout_seconds: float = 30.0
    kafka_retry_base_delay_seconds: float = 2.0
    kafka_retry_max_delay_seconds: float = 30.0

    # Verification
    max_documents_per_request: int = 5
    allowed_document_types: list[str] = ["identity", "education", "background_check"]

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
