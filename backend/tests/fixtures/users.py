"""
User factory fixtures.

Provides in-memory User and superuser instances for unit and API tests.
These are plain Python objects — NOT persisted to any database.

For integration tests that need real DB rows, call session.add(make_user()) yourself
or use seed_minimal() from tests/utils/db_helpers.py.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from app.models.user import User, UserRole
from app.core.security import hash_password


# ── Low-level factory (not a fixture) ─────────────────────────────────────────


def build_user(
    id: int = 1,
    email: str = "user@example.com",
    password: str = "Password123!",
    full_name: str = "Test User",
    job_title: str | None = "Software Engineer",
    role: UserRole = UserRole.USER,
    is_active: bool = True,
    is_superuser: bool = False,
    email_verified: bool = True,
    terms_accepted: bool = True,
) -> User:
    """
    Build an in-memory User object with sensible defaults.

    The password is automatically hashed — pass the plain-text value.

    Args:
        id:             Simulated primary key
        email:          Unique email address
        password:       Plain-text password (will be hashed)
        full_name:      Display name
        job_title:      Optional job title
        role:           UserRole enum value
        is_active:      Account active flag
        is_superuser:   Superuser flag
        email_verified: Email verified flag
        terms_accepted: ToS accepted flag

    Returns:
        User: Unsaved User instance
    """
    return User(
        id=id,
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        job_title=job_title,
        role=role,
        is_active=is_active,
        is_superuser=is_superuser,
        email_verified=email_verified,
        terms_accepted=terms_accepted,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )


def build_superuser(
    id: int = 999,
    email: str = "superuser@example.com",
    password: str = "SuperPass123!",
    full_name: str = "Super User",
) -> User:
    """
    Build an in-memory superuser.

    Convenience wrapper around build_user with superuser=True and ADMIN role.
    """
    return build_user(
        id=id,
        email=email,
        password=password,
        full_name=full_name,
        role=UserRole.ADMIN,
        is_superuser=True,
    )


def build_inactive_user(
    id: int = 2,
    email: str = "inactive@example.com",
) -> User:
    """Build a user whose account is not yet active (email not verified)."""
    return build_user(
        id=id,
        email=email,
        is_active=False,
        email_verified=False,
    )


# ── pytest fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def test_user() -> User:
    """
    Standard active USER-role user.

    Usage:
        def test_something(test_user):
            assert test_user.role == UserRole.USER
    """
    return build_user()


@pytest.fixture
def test_superuser() -> User:
    """
    Superuser for admin-protected endpoint tests.

    Usage:
        def test_admin(test_superuser):
            assert test_superuser.is_superuser is True
    """
    return build_superuser()


@pytest.fixture
def test_manager() -> User:
    """
    MANAGER-role user.

    Usage:
        def test_manager_access(test_manager):
            assert test_manager.role == UserRole.MANAGER
    """
    return build_user(
        id=10,
        email="manager@example.com",
        role=UserRole.MANAGER,
        full_name="Manager User",
    )


@pytest.fixture
def test_inactive_user() -> User:
    """
    User whose account is not active (pre-verification state).
    """
    return build_inactive_user()


@pytest.fixture
def make_user():
    """
    Parameterizable factory fixture — call it inside a test to create custom users.

    Usage:
        def test_multiple_users(make_user):
            alice = make_user(email="alice@example.com", id=10)
            bob   = make_user(email="bob@example.com",   id=11, role=UserRole.MANAGER)
    """
    return build_user
