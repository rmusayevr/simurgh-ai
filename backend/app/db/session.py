"""
Database session management.

Provides:
    - Async session factory for FastAPI endpoints
    - Sync session factory for Celery workers
    - Connection pooling configuration
    - Health check utilities

Architecture:
    - Async engine (asyncpg) for web requests
    - Sync engine (psycopg2) for background tasks
    - Separate connection pools for isolation
"""

import structlog
from typing import AsyncIterator, Iterator

from sqlalchemy import event, pool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

logger = structlog.get_logger(__name__)


# ==================== Async Engine (FastAPI) ====================


def create_async_db_engine() -> AsyncEngine:
    """
    Create async database engine for FastAPI.

    Uses asyncpg driver for high-performance async operations.
    Configured with connection pooling and timeout settings.

    Returns:
        AsyncEngine: SQLAlchemy async engine
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,  # Log SQL queries in debug mode
        future=True,  # Use SQLAlchemy 2.0 style
        pool_size=settings.DATABASE_POOL_SIZE,  # Number of persistent connections
        max_overflow=settings.DATABASE_MAX_OVERFLOW,  # Additional connections allowed
        pool_pre_ping=True,  # Test connections before using (prevents stale connections)
        pool_recycle=3600,  # Recycle connections after 1 hour
        connect_args={
            "server_settings": {
                "application_name": f"{settings.PROJECT_NAME}_web",
                "jit": "off",  # Disable JIT for better compatibility
            },
            "command_timeout": 60,  # Query timeout: 60 seconds
            "timeout": 10,  # Connection timeout: 10 seconds
        },
    )

    logger.info(
        "async_engine_created",
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        database=settings.DATABASE_URL.split("@")[-1].split("/")[0],  # Hide credentials
    )

    return engine


# Create async engine (singleton)
engine = create_async_db_engine()


# Async session factory
async_session_factory = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit (better performance)
    autoflush=False,  # Manual control over flush timing
    autocommit=False,  # Explicit transaction management
)


# ==================== Sync Engine (Celery) ====================


def create_sync_db_engine():
    """
    Create sync database engine for Celery workers.

    Uses psycopg2 driver for compatibility with sync code.
    Separate connection pool from async engine.

    Returns:
        Engine: SQLAlchemy sync engine
    """
    # Convert asyncpg URL to psycopg2
    sync_url = settings.DATABASE_URL.replace("+asyncpg://", "://").replace(
        "postgresql://", "postgresql+psycopg2://"
    )

    engine = create_engine(
        sync_url,
        echo=settings.DEBUG,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={
            "connect_timeout": 10,
        },
    )

    logger.info(
        "sync_engine_created",
        pool_size=5,
        database=sync_url.split("@")[-1].split("/")[0],
    )

    return engine


# Create sync engine (singleton)
sync_engine = create_sync_db_engine()


# ==================== Session Dependencies ====================


async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Async session dependency for FastAPI endpoints.

    Usage:
        @router.get("/items")
        async def get_items(session: AsyncSession = Depends(get_session)):
            result = await session.execute(select(Item))
            return result.scalars().all()

    Yields:
        AsyncSession: Database session

    Notes:
        - Automatically commits on success
        - Automatically rolls back on exception
        - Closes connection after request
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_session() -> Iterator[Session]:
    """
    Sync session dependency for Celery tasks.

    Usage:
        @celery_app.task
        def process_document(doc_id: int):
            with Session(sync_engine) as session:
                doc = session.get(Document, doc_id)
                ...

    Yields:
        Session: Database session
    """
    with Session(sync_engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# ==================== Health Check ====================


async def check_database_health() -> bool:
    """
    Check if database connection is healthy.

    Returns:
        bool: True if database is accessible

    Example:
        >>> if await check_database_health():
        ...     print("Database OK")
    """
    try:
        async with async_session_factory() as session:
            await session.execute("SELECT 1")
            return True
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        return False


def check_database_health_sync() -> bool:
    """
    Sync version of database health check.

    Returns:
        bool: True if database is accessible
    """
    try:
        with Session(sync_engine) as session:
            session.execute("SELECT 1")
            return True
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        return False


# ==================== Connection Pool Monitoring ====================


@event.listens_for(pool.Pool, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log new database connections."""
    logger.debug("database_connection_established")


@event.listens_for(pool.Pool, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log connection checkouts from pool."""
    logger.debug("database_connection_checked_out")


@event.listens_for(pool.Pool, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    """Log connection returns to pool."""
    logger.debug("database_connection_checked_in")


# ==================== Utilities ====================


async def get_pool_status() -> dict:
    """
    Get current connection pool status.

    Useful for monitoring and debugging.

    Returns:
        dict: Pool statistics

    Example:
        >>> status = await get_pool_status()
        >>> print(f"Active connections: {status['checked_out']}")
    """
    pool = engine.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "total": pool.size() + pool.overflow(),
    }


async def close_connections():
    """
    Close all database connections.

    Should be called during application shutdown.
    """
    logger.info("closing_database_connections")

    await engine.dispose()
    sync_engine.dispose()

    logger.info("database_connections_closed")


# ==================== Context Managers ====================


class DatabaseSession:
    """
    Context manager for database sessions with automatic error handling.

    Usage:
        async with DatabaseSession() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
    """

    def __init__(self):
        self.session: AsyncSession = None

    async def __aenter__(self) -> AsyncSession:
        self.session = async_session_factory()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.session.rollback()
            logger.warning("database_session_rolled_back", exception=str(exc_val))
        else:
            await self.session.commit()

        await self.session.close()
        return False  # Don't suppress exceptions


class SyncDatabaseSession:
    """
    Sync context manager for Celery tasks.

    Usage:
        with SyncDatabaseSession() as session:
            doc = session.get(Document, doc_id)
    """

    def __init__(self):
        self.session: Session = None

    def __enter__(self) -> Session:
        self.session = Session(sync_engine)
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.session.rollback()
            logger.warning("sync_database_session_rolled_back", exception=str(exc_val))
        else:
            self.session.commit()

        self.session.close()
        return False
