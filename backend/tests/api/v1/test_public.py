"""Phase 7 — API: Public endpoints — no auth required."""

from unittest.mock import MagicMock

BASE = "/api/v1/public"


class TestPublicHealth:
    async def test_health_returns_200(self, client):
        assert (await client.get(f"{BASE}/health")).status_code == 200

    async def test_health_status_is_healthy(self, client):
        assert (await client.get(f"{BASE}/health")).json()["status"] == "healthy"

    async def test_health_no_auth_required(self, client):
        assert (await client.get(f"{BASE}/health")).status_code != 401

    async def test_health_has_service_key(self, client):
        assert "service" in (await client.get(f"{BASE}/health")).json()


class TestPublicStatus:
    async def test_status_no_auth_required(self, client):
        resp = await client.get(f"{BASE}/status")
        assert resp.status_code != 401

    async def test_status_returns_200_with_mock(self, client):
        from app.services.system_service import SystemService

        stub = MagicMock(maintenance_mode=False, allow_registrations=True)
        original = SystemService.get_settings

        async def _m(self):
            return stub

        SystemService.get_settings = _m
        try:
            resp = await client.get(f"{BASE}/status")
            assert resp.status_code == 200
            assert "maintenance_mode" in resp.json()
        finally:
            SystemService.get_settings = original
