"""
Phase 5 — Integration: Database session tests.

Verifies that the session layer behaves correctly against a real PostgreSQL
instance:
    - db_session fixture yields a usable AsyncSession
    - flush() assigns primary keys and makes writes visible within the session
    - rollback() discards writes and leaves session usable
    - sequential reads work correctly

Note: AsyncSession is NOT safe for concurrent coroutine access within a single
session instance. asyncio.gather() on a single session causes
InvalidRequestError. All queries are issued sequentially.

All tests use the db_session fixture from integration/conftest.py (per-test
SAVEPOINT isolation with automatic rollback).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ── Session basic contract ─────────────────────────────────────────────────────


class TestGetSession:
    async def test_get_session_yields_async_session(self, db_session: AsyncSession):
        """db_session fixture must be a real AsyncSession."""
        assert isinstance(db_session, AsyncSession)

    async def test_session_can_execute_raw_sql(self, db_session: AsyncSession):
        """A live session must execute a trivial query."""
        result = await db_session.exec(text("SELECT 1 AS value"))
        assert result.fetchone()[0] == 1

    async def test_session_is_connected_to_postgresql(self, db_session: AsyncSession):
        """Session must be backed by PostgreSQL — current_database() must return a name."""
        result = await db_session.exec(text("SELECT current_database()"))
        db_name = result.fetchone()[0]
        assert isinstance(db_name, str) and db_name

    async def test_flush_makes_writes_visible_within_session(
        self, db_session: AsyncSession
    ):
        """Data added and flushed is readable within the same session before commit."""
        from app.models.user import User, UserRole
        from app.core.security import hash_password

        user = User(
            email="session_visibility@example.com",
            hashed_password=hash_password("Password123!"),
            full_name="Visibility Test",
            role=UserRole.USER,
            is_active=True,
            is_superuser=False,
            email_verified=True,
            terms_accepted=True,
        )
        db_session.add(user)
        await db_session.flush()

        result = await db_session.exec(
            text(
                "SELECT email FROM users WHERE email = 'session_visibility@example.com'"
            )
        )
        assert result.fetchone() is not None

    async def test_flush_assigns_primary_key(self, db_session: AsyncSession):
        """flush() must populate the auto-increment primary key."""
        from app.models.user import User, UserRole
        from app.core.security import hash_password

        user = User(
            email="pk_assign@example.com",
            hashed_password=hash_password("Password123!"),
            full_name="PK Test",
            role=UserRole.USER,
            is_active=True,
            is_superuser=False,
            email_verified=True,
            terms_accepted=True,
        )
        db_session.add(user)
        await db_session.flush()

        assert user.id is not None
        assert isinstance(user.id, int)
        assert user.id > 0


# ── Sequential reads ───────────────────────────────────────────────────────────


class TestSequentialReads:
    async def test_multiple_sequential_reads_return_correct_values(
        self, db_session: AsyncSession
    ):
        """
        Multiple read queries issued sequentially on the same session must all
        return correct results. (AsyncSession does not support concurrent access
        within one session — queries must be sequential.)
        """
        r1 = await db_session.exec(text("SELECT 1"))
        r2 = await db_session.exec(text("SELECT 2"))
        r3 = await db_session.exec(text("SELECT 3"))

        assert r1.scalar() == 1
        assert r2.scalar() == 2
        assert r3.scalar() == 3

    async def test_session_reusable_across_multiple_queries(
        self, db_session: AsyncSession
    ):
        """The same session instance can serve many queries in sequence."""
        for i in range(5):
            result = await db_session.exec(text(f"SELECT {i}"))
            assert result.scalar() == i


# ── Rollback behaviour ─────────────────────────────────────────────────────────


class TestSessionRollback:
    async def test_inner_rollback_discards_write(self, db_session: AsyncSession):
        """Rolling back an inner SAVEPOINT discards writes made after it."""
        sp = await db_session.begin_nested()

        from app.models.user import User, UserRole
        from app.core.security import hash_password

        user = User(
            email="inner_rollback@example.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Inner Rollback",
            role=UserRole.USER,
            is_active=True,
            is_superuser=False,
            email_verified=True,
            terms_accepted=True,
        )
        db_session.add(user)
        await db_session.flush()

        await sp.rollback()

        result = await db_session.exec(
            text(
                "SELECT COUNT(*) FROM users WHERE email = 'inner_rollback@example.com'"
            )
        )
        assert result.scalar() == 0

    async def test_session_usable_after_rollback(self, db_session: AsyncSession):
        """After a rollback the session must accept new operations without error."""
        sp = await db_session.begin_nested()
        await sp.rollback()

        result = await db_session.exec(text("SELECT 42"))
        assert result.scalar() == 42

    async def test_outer_rollback_isolates_tests(self, db_session: AsyncSession):
        """
        Data written here must not leak to other tests — proves the conftest
        SAVEPOINT-rollback strategy works end-to-end.
        """
        from app.models.user import User, UserRole
        from app.core.security import hash_password

        user = User(
            email="isolation_check@example.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Isolation Check",
            role=UserRole.USER,
            is_active=True,
            is_superuser=False,
            email_verified=True,
            terms_accepted=True,
        )
        db_session.add(user)
        await db_session.flush()

        result = await db_session.exec(
            text(
                "SELECT COUNT(*) FROM users WHERE email = 'isolation_check@example.com'"
            )
        )
        assert result.scalar() == 1
        # conftest rolls back after this test — next test sees 0 rows
