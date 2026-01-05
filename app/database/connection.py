"""Database connection and session management"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Normalize database URL to support both SQLite and Postgres (Supabase)
db_url = settings.DATABASE_URL

# If user provides a plain async Postgres URL (postgresql://) for Supabase,
# automatically upgrade it to use the asyncpg driver required by SQLAlchemy.
if db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
    normalized_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    logger.info("Normalizing DATABASE_URL for async Postgres: using asyncpg driver")
    db_url = normalized_url

# Create async engine
engine = create_async_engine(
    db_url,
    echo=settings.DEBUG,
    future=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for models
Base = declarative_base()


async def get_db_session():
    """Get database session (async generator for dependency injection)"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database - create tables"""
    from app.database.models import Call, AudioStream, AudioChunk
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database initialized")

