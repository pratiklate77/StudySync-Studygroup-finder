from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.base import Base


class DatabaseManager:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.engine = create_async_engine(
            self.settings.database_url,
            echo=False,
            pool_pre_ping=True,
        )
        self.SessionLocal = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def close_all_connections(self) -> None:
        await self.engine.dispose()


async def init_models() -> None:
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Global database manager instance
db_manager = DatabaseManager()


async def get_db() -> AsyncSession:
    async with db_manager.SessionLocal() as session:
        yield session
