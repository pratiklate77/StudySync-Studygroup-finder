from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings

class DatabaseManager:
    """
    Database Manager: Handles connections to the admin service database and peer services.
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # Admin Service Database
        self.admin_engine = create_async_engine(
            self.settings.database_url,
            echo=False,
            pool_pre_ping=True,
        )
        self.AdminSessionLocal = async_sessionmaker(
            self.admin_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Identity Service Database (Peer)
        self.identity_engine = create_async_engine(
            self.settings.identity_db_url,
            echo=False,
            pool_pre_ping=True,
        )
        self.IdentitySessionLocal = async_sessionmaker(
            self.identity_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # MongoDB Client for Session Service (Peer)
        self.mongo_client = AsyncIOMotorClient(self.settings.session_mongodb_url)
        self.session_db = self.mongo_client[self.settings.session_mongodb_db_name]

        # Group Service Database (Peer) - for group analytics
        self.group_engine = create_async_engine(
            self.settings.group_db_url,
            echo=False,
            pool_pre_ping=True,
        )
        self.GroupSessionLocal = async_sessionmaker(
            self.group_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Payment Service Database (Peer) - for revenue analytics
        self.payment_engine = create_async_engine(
            self.settings.payment_db_url,
            echo=False,
            pool_pre_ping=True,
        )
        self.PaymentSessionLocal = async_sessionmaker(
            self.payment_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def close_all_connections(self):
        """Close all database connections."""
        await self.admin_engine.dispose()
        await self.identity_engine.dispose()
        await self.group_engine.dispose()
        await self.payment_engine.dispose()
        self.mongo_client.close()


# Global database manager instance
db_manager = DatabaseManager()

# Session factories for dependency injection
AdminSessionLocal = db_manager.AdminSessionLocal


async def get_admin_db() -> AsyncSession:
    """Dependency for admin database session."""
    async with AdminSessionLocal() as session:
        yield session