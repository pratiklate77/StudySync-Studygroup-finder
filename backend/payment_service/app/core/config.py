from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://studysync:studysync_dev@localhost:5445/payment_db"
    redis_url: str = "redis://localhost:6379/6"
    kafka_bootstrap_servers: str = "kafka:29092"
    kafka_payment_events_topic: str = "PAYMENT_EVENTS"
    kafka_send_timeout_seconds: float = 5.0
    kafka_startup_timeout_seconds: float = 10.0
    kafka_startup_max_retries: int = 5
    kafka_startup_retry_delay_seconds: float = 3.0
    platform_fee_percentage: float = 10.0
    cache_ttl_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
