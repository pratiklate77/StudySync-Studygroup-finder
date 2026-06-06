from __future__ import annotations
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Admin Service Configuration: Manages all settings for the admin service.
    
    This service needs access to ALL other service databases for admin operations.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Admin Service Database (for admin users, actions, settings)
    database_url: str = (
        "postgresql+asyncpg://studysync:studysync_dev@postgres_admin:5432/admin_db"
    )
    
    # Other Services Database URLs (for admin operations)
    identity_db_url: str = (
        "postgresql+asyncpg://studysync:studysync_dev@postgres:5432/identity_db"
    )
    group_db_url: str = (
        "postgresql+asyncpg://studysync:studysync_dev@postgres_group:5432/group_db"
    )
    session_mongodb_url: str = "mongodb://mongo:27017"
    session_mongodb_db_name: str = "session_db"
    payment_db_url: str = (
        "postgresql+asyncpg://studysync:studysync_dev@postgres_payment:5432/payment_db"
    )
    
    # Redis Configuration
    redis_url: str = "redis://redis:6379/6"

    # Kafka Configuration
    kafka_bootstrap_servers: str = "kafka:29092"
    kafka_client_id: str = "admin-service"

    # Peer Service URLs
    identity_service_url: str = "http://identity_service:8000"
    group_service_url: str = "http://group_service:8002"
    
    # Admin Events Topic
    kafka_admin_events_topic: str = "ADMIN_EVENTS"
    kafka_user_events_topic: str = "USER_EVENTS"
    
    # Kafka Settings
    kafka_send_timeout_seconds: float = 5.0
    kafka_startup_timeout_seconds: float = 10.0
    kafka_startup_max_retries: int = 5
    kafka_startup_retry_delay_seconds: float = 3.0
    
    # Circuit Breaker Settings
    kafka_circuit_breaker_failure_threshold: int = 3
    kafka_circuit_breaker_recovery_timeout_seconds: float = 30.0
    
    # Retry Settings
    kafka_retry_base_delay_seconds: float = 2.0
    kafka_retry_max_delay_seconds: float = 30.0

    # JWT Configuration (for admin authentication)
    jwt_secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60  # Longer for admin sessions
    jwt_refresh_token_expire_days: int = 7

    # Admin Configuration
    super_admin_email: str = "admin@studysync.com"
    super_admin_password: str = "admin123"  # Change in production
    
    # Cache Configuration
    analytics_cache_ttl_seconds: int = 300  # 5 minutes
    user_list_cache_ttl_seconds: int = 60   # 1 minute


@lru_cache
def get_settings() -> Settings:
    """Get application settings with caching."""
    return Settings()