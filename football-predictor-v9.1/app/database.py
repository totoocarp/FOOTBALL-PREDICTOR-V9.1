"""
Football Predictor V9.0 - Database Setup
Supports SQLite (local) and PostgreSQL (production)
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from app.config import settings
from loguru import logger


class Base(DeclarativeBase):
    pass


def create_engine():
    url = settings.database_url
    if settings.is_sqlite:
        engine = create_async_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=settings.debug,
        )
        # Enable WAL mode for SQLite concurrency
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA cache_size=-32000")
            cursor.close()
    else:
        engine = create_async_engine(
            url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=settings.debug,
        )
    return engine


engine = create_engine()

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        from app.models import all_models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully")
