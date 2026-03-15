"""
Unit tests for app/middleware/maintenance.py

Covers:
    MaintenanceMiddleware.dispatch:
        - Bypass paths (/health, /api/v1/admin, /api/v1/auth, /docs, /redoc, /openapi.json,
          /static, /api/v1/system/status) always pass through regardless of maintenance state
        - Maintenance OFF → request forwarded, 200 returned
        - Maintenance ON → 503 returned, downstream NOT called
        - 503 body contains error, detail, maintenance=True, retry_after fields
        - 503 has Retry-After and X-Maintenance-Mode headers

    MaintenanceMiddleware._should_bypass (pure method):
        - Returns True for all configured bypass prefixes
        - Returns False for non-bypass paths

    MaintenanceMiddleware._refresh_maintenance_state:
        - Uses settings.MAINTENANCE_MODE when attribute exists (no DB query)
        - Caches state: does not re-read within check_interval (30s)
        - Cache invalidated when _last_check=0

    MaintenanceMiddleware class helpers:
        - enable_maintenance_mode() sets _maintenance_mode=True
        - disable_maintenance_mode() sets _maintenance_mode=False
        - get_status() returns dict with enabled, last_check, cache_age_seconds, check_interval
        - invalidate_cache() resets _last_check to 0

All DB calls are mocked. No network. No real database.
"""

import pytest
import time
from unittest.mock import MagicMock, patch


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_request(path: str = "/api/v1/proposals", client_ip: str = "1.2.3.4"):
    req = MagicMock()
    req.url = MagicMock()
    req.url.path = path
    req.method = "GET"
    req.client = MagicMock()
    req.client.host = client_ip
    return req


async def _noop_next(request):
    resp = MagicMock()
    resp.status_code = 200
    return resp


def _make_middleware():
    from app.middleware.maintenance import MaintenanceMiddleware

    # Reset class-level state before each use to avoid test bleed
    MaintenanceMiddleware._maintenance_mode = False
    MaintenanceMiddleware._last_check = 0
    MaintenanceMiddleware._cache_lock = False

    app = MagicMock()
    return MaintenanceMiddleware(app)


# ══════════════════════════════════════════════════════════════════
# _should_bypass — pure path matching
# ══════════════════════════════════════════════════════════════════


class TestShouldBypass:
    @pytest.mark.parametrize(
        "path",
        [
            "/health",
            "/health/live",
            "/api/v1/admin",
            "/api/v1/admin/users",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/api/v1/system/status",
            "/docs",
            "/docs/index.html",
            "/redoc",
            "/openapi.json",
            "/static/logo.png",
        ],
    )
    def test_bypass_paths_return_true(self, path):
        mw = _make_middleware()
        assert mw._should_bypass(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/proposals",
            "/api/v1/projects",
            "/api/v1/users/me",
            "/",
            "/favicon.ico",
        ],
    )
    def test_non_bypass_paths_return_false(self, path):
        mw = _make_middleware()
        assert mw._should_bypass(path) is False


# ══════════════════════════════════════════════════════════════════
# dispatch — bypass paths always pass through
# ══════════════════════════════════════════════════════════════════


class TestDispatchBypass:
    @pytest.mark.parametrize(
        "path",
        [
            "/health",
            "/api/v1/admin/toggle",
            "/api/v1/auth/login",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/static/app.js",
            "/api/v1/system/status",
        ],
    )
    async def test_bypass_path_passes_when_maintenance_on(self, path):
        """Bypass paths pass through even when maintenance mode is active."""
        mw = _make_middleware()
        mw.__class__._maintenance_mode = True
        mw.__class__._last_check = time.time()  # Cache fresh — won't re-read

        req = _make_request(path=path)
        called = []

        async def call_next(r):
            called.append(True)
            return await _noop_next(r)

        await mw.dispatch(req, call_next)
        assert called == [True]


# ══════════════════════════════════════════════════════════════════
# dispatch — maintenance OFF
# ══════════════════════════════════════════════════════════════════


class TestDispatchMaintenanceOff:
    async def test_normal_request_forwarded(self):
        mw = _make_middleware()
        req = _make_request()
        called = []

        async def call_next(r):
            called.append(True)
            return await _noop_next(r)

        with patch("app.middleware.maintenance.settings") as mock_settings:
            mock_settings.MAINTENANCE_MODE = False
            await mw.dispatch(req, call_next)

        assert called == [True]

    async def test_normal_request_returns_200(self):
        mw = _make_middleware()
        req = _make_request()

        async def call_next(r):
            resp = MagicMock()
            resp.status_code = 200
            return resp

        with patch("app.middleware.maintenance.settings") as mock_settings:
            mock_settings.MAINTENANCE_MODE = False
            resp = await mw.dispatch(req, call_next)

        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════
# dispatch — maintenance ON
# ══════════════════════════════════════════════════════════════════


class TestDispatchMaintenanceOn:
    async def _blocked_response(self):
        """Helper: issue a request with maintenance mode active."""
        mw = _make_middleware()
        req = _make_request(path="/api/v1/proposals")

        with patch("app.middleware.maintenance.settings") as mock_settings:
            mock_settings.MAINTENANCE_MODE = True
            return await mw.dispatch(req, _noop_next)

    async def test_maintenance_on_returns_503(self):
        resp = await self._blocked_response()
        assert resp.status_code == 503

    async def test_503_body_has_error_field(self):
        import json

        resp = await self._blocked_response()
        body = json.loads(resp.body)
        assert "error" in body

    async def test_503_body_has_detail_field(self):
        import json

        resp = await self._blocked_response()
        body = json.loads(resp.body)
        assert "detail" in body

    async def test_503_body_has_maintenance_true(self):
        import json

        resp = await self._blocked_response()
        body = json.loads(resp.body)
        assert body.get("maintenance") is True

    async def test_503_body_has_retry_after(self):
        import json

        resp = await self._blocked_response()
        body = json.loads(resp.body)
        assert "retry_after" in body
        assert body["retry_after"] > 0

    async def test_503_has_retry_after_header(self):
        resp = await self._blocked_response()
        assert "Retry-After" in resp.headers

    async def test_503_has_x_maintenance_mode_header(self):
        resp = await self._blocked_response()
        assert resp.headers.get("X-Maintenance-Mode") == "true"

    async def test_maintenance_on_does_not_call_next(self):
        mw = _make_middleware()
        req = _make_request(path="/api/v1/proposals")
        called = []

        async def call_next(r):
            called.append(True)
            return await _noop_next(r)

        with patch("app.middleware.maintenance.settings") as mock_settings:
            mock_settings.MAINTENANCE_MODE = True
            await mw.dispatch(req, call_next)

        assert called == []


# ══════════════════════════════════════════════════════════════════
# _refresh_maintenance_state — config-based (no DB)
# ══════════════════════════════════════════════════════════════════


class TestRefreshMaintenanceState:
    async def test_reads_maintenance_mode_from_settings(self):
        """When settings has MAINTENANCE_MODE, it uses that (no DB query)."""
        mw = _make_middleware()

        with patch("app.middleware.maintenance.settings") as mock_settings:
            mock_settings.MAINTENANCE_MODE = True
            await mw._refresh_maintenance_state()

        assert mw.__class__._maintenance_mode is True

    async def test_settings_false_disables_maintenance(self):
        mw = _make_middleware()
        mw.__class__._maintenance_mode = True  # pre-set

        with patch("app.middleware.maintenance.settings") as mock_settings:
            mock_settings.MAINTENANCE_MODE = False
            await mw._refresh_maintenance_state()

        assert mw.__class__._maintenance_mode is False

    async def test_cache_valid_skips_refresh(self):
        """If cache is still fresh, _refresh_maintenance_state returns immediately."""
        mw = _make_middleware()
        mw.__class__._maintenance_mode = True
        mw.__class__._last_check = time.time()  # just refreshed

        with patch("app.middleware.maintenance.settings") as mock_settings:
            mock_settings.MAINTENANCE_MODE = False  # would flip to False if read
            await mw._refresh_maintenance_state()

        # Cache was valid → settings NOT re-read → still True
        assert mw.__class__._maintenance_mode is True

    async def test_stale_cache_triggers_refresh(self):
        """Cache older than check_interval → settings are re-read."""
        mw = _make_middleware()
        mw.__class__._maintenance_mode = False
        mw.__class__._last_check = 0  # force stale

        with patch("app.middleware.maintenance.settings") as mock_settings:
            mock_settings.MAINTENANCE_MODE = True
            await mw._refresh_maintenance_state()

        assert mw.__class__._maintenance_mode is True

    async def test_lock_prevents_concurrent_refresh(self):
        """If _cache_lock is True, refresh is skipped entirely."""
        mw = _make_middleware()
        mw.__class__._maintenance_mode = False
        mw.__class__._last_check = 0  # stale
        mw.__class__._cache_lock = True  # locked

        with patch("app.middleware.maintenance.settings") as mock_settings:
            mock_settings.MAINTENANCE_MODE = True
            await mw._refresh_maintenance_state()

        # Lock blocked refresh → still False
        assert mw.__class__._maintenance_mode is False

    async def test_exception_fails_open(self):
        """DB/settings error → maintenance mode set to False (fail-open)."""
        mw = _make_middleware()
        mw.__class__._maintenance_mode = True
        mw.__class__._last_check = 0  # stale

        with patch("app.middleware.maintenance.settings") as mock_settings:
            # Simulate settings access raising an exception
            type(mock_settings).MAINTENANCE_MODE = property(
                lambda self: (_ for _ in ()).throw(RuntimeError("settings error"))
            )
            await mw._refresh_maintenance_state()

        # Fail-open: maintenance disabled when error occurs
        assert mw.__class__._maintenance_mode is False


# ══════════════════════════════════════════════════════════════════
# Class-level helpers
# ══════════════════════════════════════════════════════════════════


class TestMaintenanceHelpers:
    def setup_method(self):
        """Reset class state before each test."""
        from app.middleware.maintenance import MaintenanceMiddleware

        MaintenanceMiddleware._maintenance_mode = False
        MaintenanceMiddleware._last_check = 0
        MaintenanceMiddleware._cache_lock = False

    def test_enable_maintenance_mode_sets_true(self):
        from app.middleware.maintenance import MaintenanceMiddleware

        MaintenanceMiddleware.enable_maintenance_mode()
        assert MaintenanceMiddleware._maintenance_mode is True

    def test_enable_updates_last_check(self):
        from app.middleware.maintenance import MaintenanceMiddleware

        before = time.time() - 1
        MaintenanceMiddleware.enable_maintenance_mode()
        assert MaintenanceMiddleware._last_check >= before

    def test_disable_maintenance_mode_sets_false(self):
        from app.middleware.maintenance import MaintenanceMiddleware

        MaintenanceMiddleware._maintenance_mode = True
        MaintenanceMiddleware.disable_maintenance_mode()
        assert MaintenanceMiddleware._maintenance_mode is False

    def test_disable_updates_last_check(self):
        from app.middleware.maintenance import MaintenanceMiddleware

        before = time.time() - 1
        MaintenanceMiddleware.disable_maintenance_mode()
        assert MaintenanceMiddleware._last_check >= before

    def test_get_status_returns_enabled_key(self):
        from app.middleware.maintenance import MaintenanceMiddleware

        status = MaintenanceMiddleware.get_status()
        assert "enabled" in status

    def test_get_status_returns_last_check(self):
        from app.middleware.maintenance import MaintenanceMiddleware

        status = MaintenanceMiddleware.get_status()
        assert "last_check" in status

    def test_get_status_returns_cache_age_seconds(self):
        from app.middleware.maintenance import MaintenanceMiddleware

        status = MaintenanceMiddleware.get_status()
        assert "cache_age_seconds" in status
        assert isinstance(status["cache_age_seconds"], int)

    def test_get_status_returns_check_interval(self):
        from app.middleware.maintenance import MaintenanceMiddleware

        status = MaintenanceMiddleware.get_status()
        assert status["check_interval"] == 30

    def test_get_status_enabled_reflects_state(self):
        from app.middleware.maintenance import MaintenanceMiddleware

        MaintenanceMiddleware._maintenance_mode = True
        assert MaintenanceMiddleware.get_status()["enabled"] is True

        MaintenanceMiddleware._maintenance_mode = False
        assert MaintenanceMiddleware.get_status()["enabled"] is False

    def test_invalidate_cache_resets_last_check(self):
        from app.middleware.maintenance import MaintenanceMiddleware

        MaintenanceMiddleware._last_check = time.time()
        MaintenanceMiddleware.invalidate_cache()
        assert MaintenanceMiddleware._last_check == 0
