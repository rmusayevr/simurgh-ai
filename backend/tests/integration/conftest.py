"""
Integration test conftest.py — real PostgreSQL session management.

Strategy: nested-transaction savepoint rollback
    Each test runs inside a SAVEPOINT. After the test completes (pass or fail)
    the savepoint is rolled back, leaving the schema clean for the next test.
    This avoids the cost of TRUNCATE/DROP between tests while guaranteeing
    complete isolation.

Requirements:
    - TEST_DATABASE_URL env var must point to a live PostgreSQL instance.
    - The database schema must already exist (run `alembic upgrade head` once
      against the test DB before executing the suite).
"""

from __future__ import annotations

import os
import pytest_asyncio

from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncConnection
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# ── Resolve test database URL ──────────────────────────────────────────────────

_RAW_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test_db",
    ),
)

if _RAW_URL.startswith("postgres://"):
    _TEST_DATABASE_URL = _RAW_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif _RAW_URL.startswith("postgresql://") and "+asyncpg" not in _RAW_URL:
    _TEST_DATABASE_URL = _RAW_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    _TEST_DATABASE_URL = _RAW_URL

# ── Session factory ────────────────────────────────────────────────────────────

_TestSessionFactory = sessionmaker(
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Per-test connection ────────────────────────────────────────────────────────
#
# Function-scoped (not module-scoped) so that pytest-asyncio uses the same
# event loop for both the connection fixture and the session fixture.
# NullPool means every test gets a fresh TCP connection — no reuse issues.


@pytest_asyncio.fixture
async def db_connection() -> AsyncConnection:
    """
    Fresh async connection per test.

    Holds an open transaction (no autocommit) so the per-test SAVEPOINT
    can be rolled back after the test without affecting other tests.
    """
    engine = create_async_engine(_TEST_DATABASE_URL, poolclass=NullPool, future=True)
    async with engine.connect() as conn:
        await conn.begin()  # start the outer transaction
        yield conn
        await conn.rollback()  # roll back everything the test did
    await engine.dispose()


# ── Per-test savepoint session ────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_session(db_connection: AsyncConnection) -> AsyncSession:
    """
    Per-test AsyncSession that rolls back after each test via SAVEPOINT.

    Usage:
        async def test_create_user(db_session):
            user = User(email="a@b.com", ...)
            db_session.add(user)
            await db_session.flush()
            assert user.id is not None
            # No cleanup needed — outer rollback handles it
    """
    await db_connection.begin_nested()  # SAVEPOINT

    session = AsyncSession(bind=db_connection, expire_on_commit=False)

    @event.listens_for(session.sync_session, "after_transaction_end")
    def restart_savepoint(session_, transaction):
        if transaction.nested and not transaction._parent.nested:
            session_.begin_nested()

    try:
        yield session
    finally:
        await session.close()


# ── Convenience: empty-DB assertion ───────────────────────────────────────────


@pytest_asyncio.fixture
async def clean_db(db_session: AsyncSession):
    """
    Fixture that verifies core tables are empty before the test runs.

    Usage:
        async def test_seed_creates_rows(clean_db, db_session):
            ...
    """
    from tests.utils.db_helpers import assert_db_clean

    await assert_db_clean(db_session)
    yield db_session
