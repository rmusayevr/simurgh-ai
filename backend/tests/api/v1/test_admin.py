"""Phase 7 — API: Admin endpoints — superuser only."""

from unittest.mock import AsyncMock, patch

BASE = "/api/v1/admin"


class TestAdminAccessControl:
    """Normal users must get 403 on all admin endpoints."""

    async def test_users_endpoint_returns_403_for_normal_user(self, user_client):
        assert (await user_client.get(f"{BASE}/users")).status_code == 403

    async def test_health_endpoint_returns_403_for_normal_user(self, user_client):
        assert (await user_client.get(f"{BASE}/health")).status_code == 403

    async def test_analytics_endpoint_returns_403_for_normal_user(self, user_client):
        assert (await user_client.get(f"{BASE}/analytics")).status_code == 403

    async def test_settings_endpoint_returns_403_for_normal_user(self, user_client):
        assert (await user_client.get(f"{BASE}/settings")).status_code == 403

    async def test_prompts_endpoint_returns_403_for_normal_user(self, user_client):
        assert (await user_client.get(f"{BASE}/prompts")).status_code == 403

    async def test_unauthenticated_returns_401(self, client):
        assert (await client.get(f"{BASE}/users")).status_code == 401


class TestAdminUsers:
    async def test_get_users_returns_200_for_superuser(self, superuser_client_no_db):
        from app.services.user_service import UserService

        with patch.object(
            UserService, "admin_list_users", new=AsyncMock(return_value=[])
        ):
            resp = await superuser_client_no_db.get(f"{BASE}/users")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestAdminHealth:
    async def test_health_returns_200_for_superuser(self, superuser_client_no_db):
        from app.api.v1.endpoints.admin.health import check_database_health

        with patch.object(
            check_database_health, "__call__", new=AsyncMock(return_value=True)
        ):
            resp = await superuser_client_no_db.get(f"{BASE}/health")
        assert resp.status_code != 403


class TestAdminSettings:
    async def test_get_settings_returns_200_for_superuser(self, superuser_client):
        from app.services.system_service import SystemService
        from datetime import datetime
        from app.schemas.settings import SettingsRead

        stub = SettingsRead(
            id=1,
            maintenance_mode=False,
            maintenance_message=None,
            allow_registrations=True,
            ai_model="claude-sonnet-4-20250514",
            ai_temperature=0.7,
            ai_max_tokens=8096,
            max_debate_turns=6,
            debate_consensus_threshold=0.7,
            rag_enabled=True,
            debate_feature_enabled=True,
            thesis_mode_enabled=False,
            rate_limit_enabled=True,
            rate_limit_per_minute=60,
            max_upload_size_mb=50,
            allowed_file_types=".pdf,.docx,.txt,.md",
            email_notifications_enabled=False,
            updated_at=datetime(2024, 1, 1),
            updated_by=None,
        )
        with patch.object(
            SystemService, "get_settings", new=AsyncMock(return_value=stub)
        ):
            resp = await superuser_client.get(f"{BASE}/settings")
        assert resp.status_code == 200
