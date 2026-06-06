from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


class DatabaseManager:
    def __init__(self, database_url: str) -> None:
        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
        )
        self.SessionLocal = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def close(self) -> None:
        await self.engine.dispose()


settings = get_settings()
db_manager = DatabaseManager(settings.database_url)
AsyncSessionLocal = db_manager.SessionLocal


async def get_db() -> AsyncSession:
    async with db_manager.SessionLocal() as session:
        yield session
