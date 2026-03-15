"""
Root conftest.py — shared fixtures for the entire test suite.

Provides:
    - Environment variable patching so Settings loads without a real .env
    - Async FastAPI test client (AsyncClient)
    - In-memory async DB session backed by SQLite for unit/API tests
    - Convenience auth-header helpers

Usage:
    Every test file automatically picks up fixtures defined here.
    Integration tests override `db_session` in their own conftest.py.
"""

import os
import pytest
import pytest_asyncio
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

# ── Patch environment BEFORE app modules are imported ──────────────────────────
# This block runs at collection time, before any `from app.xxx import yyy`.
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-for-jwt-hs256")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcy0hISE=")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from httpx import AsyncClient, ASGITransport  # noqa: E402  (must come after env patch)


# ── Application import (after env is set) ──────────────────────────────────────


def _get_app():
    """Lazy import to avoid Settings validation before env vars are set."""
    from app.main import app  # adjust if your entrypoint differs

    return app


# ── pytest-asyncio mode ────────────────────────────────────────────────────────

# Configures all async tests in the suite to use asyncio automatically.
# Matches the pyproject.toml setting: asyncio_mode = "auto"


# ── HTTP client fixture ────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """
    Unauthenticated AsyncClient for API tests.

    Usage:
        async def test_public(client):
            resp = await client.get("/api/v1/public/health")
            assert resp.status_code == 200
    """
    app = _get_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── Mock DB session fixture ────────────────────────────────────────────────────


@pytest.fixture
def mock_session():
    """
    Lightweight mock AsyncSession for unit tests.

    Stubs out the most commonly-used AsyncSession methods:
        - execute  → returns a mock result (configure per-test)
        - add      → no-op
        - commit   → awaitable no-op
        - rollback → awaitable no-op
        - refresh  → awaitable no-op
        - close    → awaitable no-op

    Usage:
        async def test_something(mock_session):
            mock_session.execute.return_value = make_result([user])
            ...
    """
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    return session


# ── Auth header helpers ────────────────────────────────────────────────────────


@pytest.fixture
def auth_headers():
    """
    Factory fixture: returns a callable that produces Bearer auth headers.

    Usage:
        def test_protected(auth_headers):
            headers = auth_headers(user_id=42)
            # pass to AsyncClient requests
    """
    from app.core.security import create_access_token

    def _make_headers(user_id: int = 1, extra_claims: dict | None = None) -> dict:
        token = create_access_token(
            subject=str(user_id),
            additional_claims=extra_claims or {},
        )
        return {"Authorization": f"Bearer {token}"}

    return _make_headers


@pytest.fixture
def superuser_headers(auth_headers):
    """
    Pre-built headers for a superuser (user_id=999).

    Usage:
        async def test_admin_endpoint(client, superuser_headers):
            resp = await client.get("/api/v1/admin/users", headers=superuser_headers)
    """
    return auth_headers(user_id=999)


# ── SQLAlchemy result helper ───────────────────────────────────────────────────


def make_scalars_result(items: list):
    """
    Build a mock that mimics the return value of `await session.execute(...)`.

    Supports:
        result.scalars().all()   → items
        result.scalars().first() → items[0] or None
        result.scalar_one_or_none() → items[0] or None
        result.scalar()          → items[0] or None

    Usage (in test):
        mock_session.execute.return_value = make_scalars_result([user1, user2])
    """
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    scalars_mock.first.return_value = items[0] if items else None

    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    result_mock.scalar_one_or_none.return_value = items[0] if items else None
    result_mock.scalar.return_value = items[0] if items else None
    result_mock.all.return_value = items
    result_mock.first.return_value = items[0] if items else None
    return result_mock


# Export helper so fixtures and tests can import it directly
__all__ = ["make_scalars_result"]
