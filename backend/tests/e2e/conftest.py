"""
E2E conftest — mirrors tests/api/v1/conftest.py so that user_client,
superuser_client, and client fixtures are available to all e2e tests.
"""

from typing import AsyncIterator

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
async def user_client(app_with_user) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app_with_user), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture(loop_scope="function")
async def superuser_client(app_with_superuser) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app_with_superuser), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Unauthenticated client."""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
