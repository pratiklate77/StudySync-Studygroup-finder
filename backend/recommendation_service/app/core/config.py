from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://studysync:studysync_dev@postgres_recommendation:5432/recommendation_db"
    redis_url: str = "redis://redis:6379/8"
    
    kafka_bootstrap_servers: str = "kafka:29092"
    kafka_client_id: str = "recommendation-service"
    kafka_consumer_group: str = "recommendation-service-group"
    kafka_tutor_events_topic: str = "TUTOR_EVENTS"
    kafka_session_events_topic: str = "SESSION_EVENTS"
    kafka_rating_events_topic: str = "RATING_EVENTS"
    kafka_user_events_topic: str = "USER_EVENTS"
    kafka_startup_timeout_seconds: float = 10.0
    kafka_startup_max_retries: int = 5
    kafka_startup_retry_delay_seconds: float = 2.0
    kafka_consumer_session_timeout_ms: int = 30000
    kafka_consumer_heartbeat_interval_ms: int = 10000
    kafka_consumer_request_timeout_ms: int = 40000
    kafka_consumer_retry_backoff_ms: int = 1000
    
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"

    identity_service_url: str = "http://identity_service:8000"
    session_service_url: str = "http://session_service:8000"

    recommendation_cache_ttl: int = 600

@lru_cache
def get_settings() -> Settings:
    return Settings()