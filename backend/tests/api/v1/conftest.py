"""
API test conftest — fixtures for all Phase 7 HTTP tests.

get_current_user is overridden via dependency_overrides so tests run
without a real database. Superuser tests override get_current_superuser too.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.models.user import User, UserRole
from app.core.security import hash_password


def _stub_user(
    user_id=1, email="user@example.com", is_superuser=False, role=UserRole.USER
):
    return User(
        id=user_id,
        email=email,
        hashed_password=hash_password("Password123!"),
        full_name="Test User",
        role=role,
        is_active=True,
        is_superuser=is_superuser,
        email_verified=True,
        terms_accepted=True,
    )


@pytest.fixture
def app_with_user():
    from app.main import app
    from app.api.v1.dependencies import get_current_user

    stub = _stub_user()
    app.dependency_overrides[get_current_user] = lambda: stub
    yield app
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def app_with_superuser():
    from app.main import app
    from app.api.v1.dependencies import get_current_user, get_current_superuser

    stub = _stub_user(user_id=999, is_superuser=True, role=UserRole.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: stub
    app.dependency_overrides[get_current_superuser] = lambda: stub
    yield app
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_superuser, None)


@pytest_asyncio.fixture(loop_scope="function")
async def user_client(app_with_user):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_user), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture(loop_scope="function")
async def superuser_client(app_with_superuser):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_superuser), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def app_with_superuser_no_db():
    """App with superuser auth AND a mock DB session (no real DB needed)."""
    from app.main import app
    from app.api.v1.dependencies import get_current_user, get_session

    stub_user = User(
        id=999,
        email="admin@example.com",
        hashed_password=hash_password("Password123!"),
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
        is_superuser=True,
        email_verified=True,
        terms_accepted=True,
    )
    stub_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = None
    stub_session.exec = AsyncMock(return_value=mock_result)
    stub_session.add = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: stub_user
    app.dependency_overrides[get_session] = lambda: stub_session
    yield app
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_session, None)


@pytest_asyncio.fixture
async def superuser_client_no_db(app_with_superuser_no_db):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_superuser_no_db), base_url="http://test"
    ) as ac:
        yield ac


from typing import AsyncIterator


@pytest_asyncio.fixture
async def unauthed_client() -> AsyncIterator[AsyncClient]:
    """Unauthenticated HTTP client — alias used by auth-guard tests."""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def authed_client(app_with_user) -> AsyncIterator[AsyncClient]:
    """Authenticated HTTP client (regular user) — alias used by auth-guard tests."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_user), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def app_with_user_no_db():
    """App with user auth AND a mock DB session (no real DB needed)."""
    from app.main import app
    from app.api.v1.dependencies import get_current_user, get_session

    stub_user = _stub_user()
    stub_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = None
    stub_session.exec = AsyncMock(return_value=mock_result)
    stub_session.add = MagicMock()

    mock_participant = MagicMock()
    mock_participant.user_id = 1

    async def mock_get(model, pk):
        return mock_participant

    stub_session.get = mock_get

    app.dependency_overrides[get_current_user] = lambda: stub_user
    app.dependency_overrides[get_session] = lambda: stub_session
    yield app
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_session, None)


@pytest_asyncio.fixture
async def user_client_no_db(app_with_user_no_db):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_user_no_db), base_url="http://test"
    ) as ac:
        yield ac
