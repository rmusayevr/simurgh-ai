"""
Phase 6 — Integration: UserService against real PostgreSQL.

Covers:
    - create user → persists with hashed password
    - fetch by email returns correct record
    - update role persists change
    - duplicate email raises ConflictException
    - authenticate returns user and increments login_count
    - change_password hashes the new password (no plaintext stored)
    - revoke_all_user_tokens clears active refresh tokens
"""

from __future__ import annotations

import pytest

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.models.user import User, UserRole
from app.models.token import RefreshToken
from app.core.security import hash_password, verify_password
from app.core.exceptions import (
    ConflictException,
    UnauthorizedException,
    BadRequestException,
)
from app.schemas.user import UserCreate, ChangePasswordRequest, AdminUserUpdate
from app.services.user_service import UserService


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_user(
    email: str, password: str = "Password123!", role: UserRole = UserRole.USER
) -> User:
    return User(
        email=email,
        hashed_password=hash_password(password),
        full_name="Test User",
        role=role,
        is_active=True,
        is_superuser=False,
        email_verified=True,
        terms_accepted=True,
    )


# ── Create ─────────────────────────────────────────────────────────────────────


class TestCreateUser:
    async def test_register_persists_user_to_db(self, db_session: AsyncSession):
        """register() must write a row to the users table."""
        svc = UserService(db_session)
        data = UserCreate(
            email="register@example.com",
            password="Password123!",
            confirm_password="Password123!",
            full_name="New User",
        )
        user = await svc.register(data)

        assert user.id is not None
        fetched = await db_session.get(User, user.id)
        assert fetched is not None
        assert fetched.email == "register@example.com"

    async def test_register_hashes_password(self, db_session: AsyncSession):
        """Password must be stored as a bcrypt hash, not plaintext."""
        svc = UserService(db_session)
        data = UserCreate(
            email="hashcheck@example.com",
            password="PlainText1Pass!",
            confirm_password="PlainText1Pass!",
            full_name="Hash Check",
        )
        user = await svc.register(data)

        assert user.hashed_password != "PlainText1Pass!"
        assert verify_password("PlainText1Pass!", user.hashed_password)

    async def test_register_duplicate_email_raises_conflict(
        self, db_session: AsyncSession
    ):
        """Second registration with same email must raise ConflictException."""
        svc = UserService(db_session)
        data = UserCreate(
            email="dup@example.com",
            password="Password123!",
            confirm_password="Password123!",
            full_name="Dup User",
        )
        await svc.register(data)

        with pytest.raises(ConflictException):
            await svc.register(data)

    async def test_register_email_stored_lowercase(self, db_session: AsyncSession):
        """Email must be normalised to lowercase on registration."""
        svc = UserService(db_session)
        data = UserCreate(
            email="UPPER@Example.COM",
            password="Password123!",
            confirm_password="Password123!",
            full_name="Case User",
        )
        user = await svc.register(data)
        assert user.email == "upper@example.com"


# ── Read ───────────────────────────────────────────────────────────────────────


class TestFetchUser:
    async def test_get_by_email_returns_correct_record(self, db_session: AsyncSession):
        """get_by_email() must return the right user."""
        user = _make_user("fetch@example.com")
        db_session.add(user)
        await db_session.flush()

        svc = UserService(db_session)
        found = await svc.get_by_email("fetch@example.com")

        assert found is not None
        assert found.id == user.id

    async def test_get_by_email_returns_none_for_unknown(
        self, db_session: AsyncSession
    ):
        """get_by_email() must return None when no match."""
        svc = UserService(db_session)
        result = await svc.get_by_email("nobody@example.com")
        assert result is None

    async def test_get_by_id_returns_correct_user(self, db_session: AsyncSession):
        """get_by_id() must return the user with matching primary key."""
        user = _make_user("byid@example.com")
        db_session.add(user)
        await db_session.flush()

        svc = UserService(db_session)
        found = await svc.get_by_id(user.id)
        assert found.email == "byid@example.com"


# ── Update ────────────────────────────────────────────────────────────────────


class TestUpdateUser:
    async def test_admin_update_role_persists_to_db(self, db_session: AsyncSession):
        """admin_update_user() role change must survive a DB round-trip."""
        user = _make_user("rolechange@example.com", role=UserRole.USER)
        db_session.add(user)
        await db_session.flush()

        svc = UserService(db_session)
        data = AdminUserUpdate(role=UserRole.MANAGER)
        updated = await svc.admin_update_user(user.id, data)

        assert updated.role == UserRole.MANAGER

        # Verify it's really in the DB
        await db_session.refresh(updated)
        assert updated.role == UserRole.MANAGER

    async def test_admin_update_email_lowercases_value(self, db_session: AsyncSession):
        """admin_update_user() must normalise new email to lowercase."""
        user = _make_user("old@example.com")
        db_session.add(user)
        await db_session.flush()

        svc = UserService(db_session)
        data = AdminUserUpdate(email="NEW@Example.COM")
        updated = await svc.admin_update_user(user.id, data)

        assert updated.email == "new@example.com"


# ── Authentication ────────────────────────────────────────────────────────────


class TestAuthenticate:
    async def test_authenticate_returns_user_on_valid_credentials(
        self, db_session: AsyncSession
    ):
        """authenticate() must return the user when credentials are correct."""
        user = _make_user("auth@example.com", password="Correct123!")
        db_session.add(user)
        await db_session.flush()

        svc = UserService(db_session)
        result = await svc.authenticate("auth@example.com", "Correct123!")

        assert result.id == user.id

    async def test_authenticate_increments_login_count(self, db_session: AsyncSession):
        """Successful authenticate() must increment login_count."""
        user = _make_user("logincount@example.com", password="Pass123!")
        db_session.add(user)
        await db_session.flush()
        initial_count = user.login_count

        svc = UserService(db_session)
        result = await svc.authenticate("logincount@example.com", "Pass123!")

        assert result.login_count == initial_count + 1

    async def test_authenticate_wrong_password_raises_unauthorized(
        self, db_session: AsyncSession
    ):
        """authenticate() with wrong password must raise UnauthorizedException."""
        user = _make_user("wrongpass@example.com", password="Correct123!")
        db_session.add(user)
        await db_session.flush()

        svc = UserService(db_session)
        with pytest.raises(UnauthorizedException):
            await svc.authenticate("wrongpass@example.com", "WrongPass!")

    async def test_authenticate_unknown_email_raises_unauthorized(
        self, db_session: AsyncSession
    ):
        """authenticate() with unknown email must raise UnauthorizedException."""
        svc = UserService(db_session)
        with pytest.raises(UnauthorizedException):
            await svc.authenticate("ghost@example.com", "Password123!")


# ── Password change ───────────────────────────────────────────────────────────


class TestChangePassword:
    async def test_change_password_hashes_new_password(self, db_session: AsyncSession):
        """change_password() must store the new password as a hash, not plaintext."""
        user = _make_user("changepw@example.com", password="OldPass123!")
        db_session.add(user)
        await db_session.flush()

        svc = UserService(db_session)
        data = ChangePasswordRequest(
            current_password="OldPass123!",
            new_password="NewPass456!",
            confirm_new_password="NewPass456!",
        )
        updated = await svc.change_password(user.id, data)

        assert updated.hashed_password != "NewPass456!"
        assert verify_password("NewPass456!", updated.hashed_password)

    async def test_change_password_wrong_current_raises_bad_request(
        self, db_session: AsyncSession
    ):
        """change_password() with wrong current_password must raise BadRequestException."""
        user = _make_user("badcurrent@example.com", password="RealPass123!")
        db_session.add(user)
        await db_session.flush()

        svc = UserService(db_session)
        data = ChangePasswordRequest(
            current_password="WrongOldPass!",
            new_password="NewPass456!",
            confirm_new_password="NewPass456!",
        )
        with pytest.raises(BadRequestException):
            await svc.change_password(user.id, data)


# ── Token revocation ──────────────────────────────────────────────────────────


class TestTokenRevocation:
    async def test_revoke_all_tokens_clears_active_tokens(
        self, db_session: AsyncSession
    ):
        """revoke_all_user_tokens() must set revoked_at on every active token."""
        from datetime import datetime, timezone, timedelta

        user = _make_user("revoke@example.com")
        db_session.add(user)
        await db_session.flush()

        # Add two active refresh tokens
        for i in range(2):
            token = RefreshToken(
                user_id=user.id,
                token=f"token-{i}-{user.id}",
                expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                + timedelta(days=7),
            )
            db_session.add(token)
        await db_session.flush()

        svc = UserService(db_session)
        await svc.revoke_all_user_tokens(user.id)

        result = await db_session.exec(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        active_tokens = result.all()
        assert len(active_tokens) == 0
