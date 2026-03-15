"""Phase 7 - API: Thesis metrics endpoints (auth guards only)."""

from __future__ import annotations
from httpx import AsyncClient

BASE = "/api/v1/thesis"


class TestThesisMetricsAuthGuards:
    async def test_get_metrics_without_auth_returns_401(
        self, unauthed_client: AsyncClient
    ):
        resp = await unauthed_client.get(f"{BASE}/export/persona-codings")
        assert resp.status_code == 401

    async def test_get_metrics_with_auth_returns_non_401(
        self, user_client_no_db: AsyncClient
    ):
        """Authenticated superuser request must not return 401.

        Uses user_client_no_db because the thesis export endpoint calls
        get_session directly. The no_db fixture overrides get_session so no
        real PostgreSQL connection is needed in the API test tier.
        """
        resp = await user_client_no_db.get(f"{BASE}/export/persona-codings")
        assert resp.status_code != 401
