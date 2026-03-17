"""Phase 7 — API: Authentication endpoints."""

from unittest.mock import AsyncMock, patch
from app.models.user import User, UserRole
from app.core.security import hash_password

BASE = "/api/v1/auth"


def _user(uid=1, email="test@example.com"):
    u = User(
        id=uid,
        email=email,
        hashed_password=hash_password("Password123!"),
        full_name="Test",
        role=UserRole.USER,
        is_active=True,
        is_superuser=False,
        email_verified=True,
        terms_accepted=True,
        verification_token="tok",
    )
    return u


class TestRegister:
    async def test_register_returns_201(self, user_client_no_db):
        from app.services.user_service import UserService
        from app.services.system_service import SystemService
        from app.core.config import settings

        mock_settings = AsyncMock()
        mock_settings.allow_registrations = True
        with patch.object(
            SystemService, "get_settings", new=AsyncMock(return_value=mock_settings)
        ):
            with patch.object(
                UserService, "register", new=AsyncMock(return_value=_user())
            ):
                with patch.object(settings, "SKIP_EMAIL_VERIFICATION", True):
                    resp = await user_client_no_db.post(
                        f"{BASE}/register",
                        json={
                            "email": "new@example.com",
                            "password": "Password123!",
                            "confirm_password": "Password123!",
                            "full_name": "New User",
                            "terms_accepted": True,
                        },
                    )
        assert resp.status_code == 201

    async def test_register_returns_message_key(self, user_client_no_db):
        from app.services.user_service import UserService
        from app.services.system_service import SystemService
        from app.core.config import settings

        mock_settings = AsyncMock()
        mock_settings.allow_registrations = True
        with patch.object(
            SystemService, "get_settings", new=AsyncMock(return_value=mock_settings)
        ):
            with patch.object(
                UserService, "register", new=AsyncMock(return_value=_user())
            ):
                with patch.object(settings, "SKIP_EMAIL_VERIFICATION", True):
                    resp = await user_client_no_db.post(
                        f"{BASE}/register",
                        json={
                            "email": "msg@example.com",
                            "password": "Password123!",
                            "confirm_password": "Password123!",
                            "full_name": "Msg",
                            "terms_accepted": True,
                        },
                    )
        assert "message" in resp.json()

    async def test_register_invalid_email_returns_422(self, client):
        resp = await client.post(
            f"{BASE}/register", json={"email": "bad", "password": "x"}
        )
        assert resp.status_code == 422

    async def test_register_mismatched_passwords_returns_422(self, client):
        resp = await client.post(
            f"{BASE}/register",
            json={
                "email": "a@b.com",
                "password": "Password123!",
                "confirm_password": "Different1!",
                "full_name": "A",
            },
        )
        assert resp.status_code == 422


class TestLogin:
    async def test_login_returns_200_with_tokens(self, client):
        from app.services.user_service import UserService

        with (
            patch.object(
                UserService, "authenticate", new=AsyncMock(return_value=_user())
            ),
            patch.object(
                UserService, "issue_tokens", new=AsyncMock(return_value=("acc", "ref"))
            ),
        ):
            resp = await client.post(
                f"{BASE}/token",
                data={"username": "test@example.com", "password": "Password123!"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body and "refresh_token" in body
        assert body["token_type"] == "bearer"

    async def test_login_wrong_creds_returns_401(self, client):
        from app.services.user_service import UserService
        from app.core.exceptions import UnauthorizedException

        with patch.object(
            UserService,
            "authenticate",
            new=AsyncMock(side_effect=UnauthorizedException("bad")),
        ):
            resp = await client.post(
                f"{BASE}/token", data={"username": "x", "password": "y"}
            )
        assert resp.status_code == 401

    async def test_login_missing_fields_returns_422(self, client):
        assert (await client.post(f"{BASE}/token", data={})).status_code == 422


class TestGetMe:
    async def test_me_without_token_returns_401(self, client):
        assert (await client.get(f"{BASE}/me")).status_code == 401

    async def test_me_with_override_returns_200(self, user_client):
        resp = await user_client.get(f"{BASE}/me")
        assert resp.status_code == 200

    async def test_me_response_has_email(self, user_client):
        resp = await user_client.get(f"{BASE}/me")
        assert resp.status_code == 200
        assert "email" in resp.json()


class TestRefreshToken:
    async def test_refresh_returns_new_access_token(self, client):
        from app.services.user_service import UserService

        with patch.object(
            UserService, "refresh_access_token", new=AsyncMock(return_value="new_acc")
        ):
            resp = await client.post(
                f"{BASE}/refresh", json={"refresh_token": "ref_tok"}
            )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_refresh_bad_token_returns_401(self, client):
        from app.services.user_service import UserService
        from app.core.exceptions import UnauthorizedException

        with patch.object(
            UserService,
            "refresh_access_token",
            new=AsyncMock(side_effect=UnauthorizedException("bad")),
        ):
            resp = await client.post(f"{BASE}/refresh", json={"refresh_token": "bad"})
        assert resp.status_code == 401


class TestChangePassword:
    async def test_change_password_returns_200(self, user_client):
        from app.services.user_service import UserService

        with patch.object(
            UserService, "change_password", new=AsyncMock(return_value=None)
        ):
            resp = await user_client.post(
                f"{BASE}/me/change-password",
                json={
                    "current_password": "OldPass1!",
                    "new_password": "NewPass1!",
                    "confirm_new_password": "NewPass1!",
                },
            )
        assert resp.status_code == 200

    async def test_change_password_requires_auth(self, client):
        resp = await client.post(
            f"{BASE}/me/change-password",
            json={
                "current_password": "A",
                "new_password": "B",
                "confirm_new_password": "B",
            },
        )
        assert resp.status_code == 401
