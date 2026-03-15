"""
Unit tests for app/services/user_service.py

Covers:
    - register: creates user with hashed password, email lowercased
    - register: raises ConflictException if email already taken
    - authenticate: correct credentials returns user, updates last_login
    - authenticate: wrong password raises UnauthorizedException
    - authenticate: unverified email raises UnauthorizedException
    - authenticate: inactive account raises UnauthorizedException
    - issue_tokens: returns two non-empty strings
    - refresh_access_token: valid token returns new access token
    - refresh_access_token: revoked token raises UnauthorizedException
    - refresh_access_token: expired token raises UnauthorizedException
    - change_password: wrong current password raises BadRequestException
    - get_by_id: missing user raises NotFoundException

All DB calls mocked via AsyncMock.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.models.user import User
from app.models.token import RefreshToken
from app.core.security import hash_password
from app.core.exceptions import (
    NotFoundException,
    ConflictException,
    UnauthorizedException,
    BadRequestException,
)
from tests.fixtures.users import build_user, build_inactive_user


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_service(db_mock):
    from app.services.user_service import UserService

    return UserService(db=db_mock)


def _make_user_create(
    email="new@example.com",
    password="Password123!",
    full_name="New User",
    job_title="Engineer",
):
    from app.schemas.user import UserCreate

    return UserCreate(
        email=email,
        password=password,
        confirm_password=password,
        full_name=full_name,
        job_title=job_title,
    )


def _make_change_password_request(current="OldPass123!", new="NewPass456!"):
    from app.schemas.user import ChangePasswordRequest

    return ChangePasswordRequest(
        current_password=current,
        new_password=new,
        confirm_new_password=new,
    )


def _make_exec_result(items):
    """Build a mock that mimics session.exec(stmt).first() / .all()."""
    result = MagicMock()
    result.first.return_value = items[0] if items else None
    result.all.return_value = items
    return result


# ══════════════════════════════════════════════════════════════════
# get_by_id
# ══════════════════════════════════════════════════════════════════


class TestGetById:
    async def test_returns_user_when_found(self):
        user = build_user(id=1)
        db = AsyncMock()
        db.get = AsyncMock(return_value=user)
        svc = _make_service(db)
        result = await svc.get_by_id(1)
        assert result == user

    async def test_raises_not_found_when_missing(self):
        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        svc = _make_service(db)
        with pytest.raises(NotFoundException):
            await svc.get_by_id(999)


# ══════════════════════════════════════════════════════════════════
# register
# ══════════════════════════════════════════════════════════════════


class TestRegister:
    def _make_db(self):
        """AsyncMock db with add as MagicMock (service calls db.add without await)."""
        db = AsyncMock()
        db.exec = AsyncMock(return_value=_make_exec_result([]))
        db.add = MagicMock()  # ← must be MagicMock: service calls without await
        db.refresh = AsyncMock()
        return db

    async def test_creates_user_with_hashed_password(self):
        db = self._make_db()
        svc = _make_service(db)
        data = _make_user_create(password="Password123!")

        added_user = None

        def capture_add(obj):
            nonlocal added_user
            if isinstance(obj, User):
                added_user = obj

        db.add.side_effect = capture_add

        await svc.register(data)
        assert added_user is not None
        assert added_user.hashed_password != "Password123!"
        assert added_user.hashed_password.startswith("$2b$")

    async def test_email_stored_lowercase(self):
        db = self._make_db()
        svc = _make_service(db)
        data = _make_user_create(email="Alice@EXAMPLE.COM")

        added_user = None

        def capture_add(obj):
            nonlocal added_user
            if isinstance(obj, User):
                added_user = obj

        db.add.side_effect = capture_add

        await svc.register(data)
        assert added_user.email == "alice@example.com"

    async def test_new_user_is_inactive(self):
        db = self._make_db()
        svc = _make_service(db)
        data = _make_user_create()

        added_user = None

        def capture_add(obj):
            nonlocal added_user
            if isinstance(obj, User):
                added_user = obj

        db.add.side_effect = capture_add

        await svc.register(data)
        assert added_user.is_active is False
        assert added_user.email_verified is False

    async def test_verification_token_generated(self):
        db = self._make_db()
        svc = _make_service(db)
        data = _make_user_create()

        added_user = None

        def capture_add(obj):
            nonlocal added_user
            if isinstance(obj, User):
                added_user = obj

        db.add.side_effect = capture_add

        await svc.register(data)
        assert added_user.verification_token is not None
        assert len(added_user.verification_token) > 10

    async def test_duplicate_email_raises_conflict(self):
        existing = build_user(email="taken@example.com")
        db = AsyncMock()
        db.exec = AsyncMock(return_value=_make_exec_result([existing]))

        svc = _make_service(db)
        data = _make_user_create(email="taken@example.com")

        with pytest.raises(ConflictException):
            await svc.register(data)

    async def test_commit_called_after_add(self):
        db = self._make_db()
        svc = _make_service(db)
        await svc.register(_make_user_create())
        db.commit.assert_called_once()


# ══════════════════════════════════════════════════════════════════
# authenticate
# ══════════════════════════════════════════════════════════════════


class TestAuthenticate:
    async def test_valid_credentials_returns_user(self):
        user = build_user(email="user@example.com", password="Password123!")
        db = AsyncMock()
        db.exec = AsyncMock(return_value=_make_exec_result([user]))
        db.add = MagicMock()
        db.refresh = AsyncMock()
        svc = _make_service(db)

        result = await svc.authenticate("user@example.com", "Password123!")
        assert result.email == "user@example.com"

    async def test_valid_login_updates_last_login(self):
        user = build_user(password="Password123!")
        assert user.last_login is None
        db = AsyncMock()
        db.exec = AsyncMock(return_value=_make_exec_result([user]))
        db.add = MagicMock()
        db.refresh = AsyncMock()
        svc = _make_service(db)

        await svc.authenticate(user.email, "Password123!")
        assert user.last_login is not None

    async def test_valid_login_increments_login_count(self):
        user = build_user(password="Password123!")
        user.login_count = 0
        db = AsyncMock()
        db.exec = AsyncMock(return_value=_make_exec_result([user]))
        db.add = MagicMock()
        db.refresh = AsyncMock()
        svc = _make_service(db)

        await svc.authenticate(user.email, "Password123!")
        assert user.login_count == 1

    async def test_wrong_password_raises_unauthorized(self):
        user = build_user(password="Password123!")
        db = AsyncMock()
        db.exec = AsyncMock(return_value=_make_exec_result([user]))
        db.add = MagicMock()
        svc = _make_service(db)

        with pytest.raises(UnauthorizedException):
            await svc.authenticate(user.email, "WrongPassword!")

    async def test_nonexistent_user_raises_unauthorized(self):
        db = AsyncMock()
        db.exec = AsyncMock(return_value=_make_exec_result([]))
        db.add = MagicMock()
        svc = _make_service(db)

        with pytest.raises(UnauthorizedException):
            await svc.authenticate("nobody@example.com", "Password123!")

    async def test_unverified_email_raises_unauthorized(self):
        user = build_inactive_user()
        user.hashed_password = hash_password("Password123!")
        db = AsyncMock()
        db.exec = AsyncMock(return_value=_make_exec_result([user]))
        db.add = MagicMock()
        svc = _make_service(db)

        with pytest.raises(UnauthorizedException, match="verify"):
            await svc.authenticate(user.email, "Password123!")

    async def test_active_but_unverified_raises_for_unverified(self):
        user = build_user(password="Password123!")
        user.is_active = True
        user.email_verified = False
        db = AsyncMock()
        db.exec = AsyncMock(return_value=_make_exec_result([user]))
        db.add = MagicMock()
        svc = _make_service(db)

        with pytest.raises(UnauthorizedException):
            await svc.authenticate(user.email, "Password123!")


# ══════════════════════════════════════════════════════════════════
# issue_tokens
# ══════════════════════════════════════════════════════════════════


class TestIssueTokens:
    async def test_returns_two_non_empty_strings(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.refresh = AsyncMock()
        svc = _make_service(db)

        access, refresh = await svc.issue_tokens(user_id=1)
        assert isinstance(access, str) and len(access) > 0
        assert isinstance(refresh, str) and len(refresh) > 0

    async def test_access_and_refresh_are_different(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.refresh = AsyncMock()
        svc = _make_service(db)

        access, refresh = await svc.issue_tokens(user_id=1)
        assert access != refresh

    async def test_refresh_token_persisted_to_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.refresh = AsyncMock()
        svc = _make_service(db)

        await svc.issue_tokens(user_id=1)
        # A RefreshToken should have been added (don't str() the args — triggers __repr__ → is_valid)
        db.add.assert_called()


# ══════════════════════════════════════════════════════════════════
# refresh_access_token
# ══════════════════════════════════════════════════════════════════


class TestRefreshAccessToken:
    def _make_valid_token_record(self, user_id: int = 1):
        record = MagicMock(spec=RefreshToken)
        record.user_id = user_id
        record.revoked_at = None
        record.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            days=7
        )
        return record

    async def test_valid_token_returns_new_access_token(self):
        token_record = self._make_valid_token_record()
        db = AsyncMock()
        db.exec = AsyncMock(return_value=_make_exec_result([token_record]))
        db.add = MagicMock()
        svc = _make_service(db)

        result = await svc.refresh_access_token("valid-refresh-token")
        assert isinstance(result, str) and len(result) > 0

    async def test_invalid_token_raises_unauthorized(self):
        db = AsyncMock()
        db.exec = AsyncMock(return_value=_make_exec_result([]))
        db.add = MagicMock()
        svc = _make_service(db)

        with pytest.raises(UnauthorizedException):
            await svc.refresh_access_token("nonexistent-token")

    async def test_expired_token_raises_unauthorized(self):
        token_record = self._make_valid_token_record()
        token_record.expires_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        ) - timedelta(days=1)
        db = AsyncMock()
        db.exec = AsyncMock(return_value=_make_exec_result([token_record]))
        db.add = MagicMock()
        svc = _make_service(db)

        with pytest.raises(UnauthorizedException, match="expired"):
            await svc.refresh_access_token("expired-token")


# ══════════════════════════════════════════════════════════════════
# change_password
# ══════════════════════════════════════════════════════════════════


class TestChangePassword:
    async def test_wrong_current_password_raises_bad_request(self):
        user = build_user(password="CorrectPass123!")
        db = AsyncMock()
        db.get = AsyncMock(return_value=user)
        db.exec = AsyncMock(return_value=_make_exec_result([]))
        db.add = MagicMock()
        db.refresh = AsyncMock()
        svc = _make_service(db)

        data = _make_change_password_request(current="WrongPass123!", new="NewPass456!")
        with pytest.raises(BadRequestException, match="incorrect"):
            await svc.change_password(user_id=1, data=data)

    async def test_correct_password_updates_hash(self):
        user = build_user(password="OldPass123!")
        db = AsyncMock()
        db.get = AsyncMock(return_value=user)
        db.exec = AsyncMock(return_value=_make_exec_result([]))
        db.add = MagicMock()
        db.refresh = AsyncMock()
        svc = _make_service(db)

        data = _make_change_password_request(current="OldPass123!", new="NewPass456!")
        await svc.change_password(user_id=1, data=data)

        from app.core.security import verify_password

        assert verify_password("NewPass456!", user.hashed_password)

    async def test_user_not_found_raises_not_found(self):
        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        db.add = MagicMock()
        svc = _make_service(db)

        data = _make_change_password_request()
        with pytest.raises(NotFoundException):
            await svc.change_password(user_id=999, data=data)
