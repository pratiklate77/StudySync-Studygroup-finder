from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://studysync:studysync_dev@postgres_notification:5432/notification_db"

    # Redis
    redis_url: str = "redis://redis:6379/7"
    notification_cache_ttl_seconds: int = 300
    unread_count_cache_ttl_seconds: int = 60
    preferences_cache_ttl_seconds: int = 600

    # Kafka
    kafka_bootstrap_servers: str = "kafka:29092"
    kafka_client_id: str = "notification-service"
    kafka_consumer_group: str = "notification-service-group"
    kafka_startup_timeout_seconds: float = 10.0
    kafka_startup_max_retries: int = 5
    kafka_startup_retry_delay_seconds: float = 3.0
    kafka_consumer_session_timeout_ms: int = 30000
    kafka_consumer_heartbeat_interval_ms: int = 10000
    kafka_consumer_request_timeout_ms: int = 40000
    kafka_consumer_retry_backoff_ms: int = 1000
    kafka_send_timeout_seconds: float = 5.0
    kafka_circuit_breaker_failure_threshold: int = 3
    kafka_circuit_breaker_recovery_timeout_seconds: float = 30.0
    kafka_retry_base_delay_seconds: float = 2.0
    kafka_retry_max_delay_seconds: float = 60.0

    # Kafka topics to consume
    kafka_user_events_topic: str = "USER_EVENTS"
    kafka_session_events_topic: str = "SESSION_EVENTS"
    kafka_group_events_topic: str = "GROUP_EVENTS"
    kafka_payment_events_topic: str = "PAYMENT_EVENTS"
    kafka_verification_events_topic: str = "VERIFICATION_EVENTS"
    kafka_chat_events_topic: str = "CHAT_EVENTS"
    kafka_recommendation_events_topic: str = "RECOMMENDATION_EVENTS"
    kafka_rating_events_topic: str = "RATING_EVENTS"
    kafka_admin_events_topic: str = "ADMIN_EVENTS"

    # Kafka topics to produce
    kafka_notification_events_topic: str = "NOTIFICATION_EVENTS"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"

    # Inter-service URLs
    identity_service_url: str = "http://identity_service:8000"
    session_service_url: str = "http://session_service:8001"
    group_service_url: str = "http://group_service:8002"
    payment_service_url: str = "http://payment_service:8005"
    verification_service_url: str = "http://verification_service:8006"

    # SMTP / Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@studysync.com"
    smtp_use_tls: bool = False
    smtp_start_tls: bool = True
    app_base_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
