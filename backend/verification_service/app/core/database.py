from typing import AsyncIterator, AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from app.core.config import get_settings
from app.models.base import Base


class DatabaseManager:
    """Manages database connections and session creation."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=20,
            max_overflow=10,
        )
        self.SessionLocal = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    async def init_tables(self) -> None:
        """Create all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def close(self) -> None:
        """Close database connection."""
        await self.engine.dispose()
    
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """Get database session."""
        async with self.SessionLocal() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


# Initialize database manager
settings = get_settings()
db_manager = DatabaseManager(settings.database_url)
AsyncSessionLocal = db_manager.SessionLocal

# Dependency for FastAPI routes – provides a DB session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_models() -> None:
    """Initialize database models."""
    await db_manager.init_tables()


async def init_db(settings) -> None:
    """Re-initialize db_manager with settings (called from lifespan)."""
    global db_manager, AsyncSessionLocal
    db_manager = DatabaseManager(settings.database_url)
    AsyncSessionLocal = db_manager.SessionLocal
    await db_manager.init_tables()
