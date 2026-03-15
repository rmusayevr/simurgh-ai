"""Phase 7 — API: Exit survey endpoints."""

BASE = "/api/v1/experiment"


def _payload():
    return {
        "preferred_system": "MULTIAGENT",
        "preferred_system_reason": "More balanced",
        "most_useful_aspect": "Persona diversity",
        "least_useful_aspect": "Length",
        "would_use_in_practice": True,
        "additional_comments": "Great tool",
        "nps_score": 8,
    }


class TestSubmitExitSurvey:
    async def test_submit_requires_auth(self, client):
        assert (
            await client.post(f"{BASE}/exit-survey", json=_payload())
        ).status_code == 401

    async def test_submit_missing_required_field_returns_422(self, user_client):
        resp = await user_client.post(
            f"{BASE}/exit-survey", json={"preferred_system": "MULTIAGENT"}
        )
        assert resp.status_code == 422

    async def test_submit_authenticated_not_401(self, user_client):
        """With auth header the endpoint is reachable (200/201/409/422, never 401)."""
        resp = await user_client.post(f"{BASE}/exit-survey", json=_payload())
        assert resp.status_code != 401


class TestGetMyExitSurvey:
    async def test_get_me_requires_auth(self, client):
        assert (await client.get(f"{BASE}/exit-survey/me")).status_code == 401

    async def test_get_me_authenticated_not_401(self, user_client_no_db):
        """Authenticated request: 200 (found) or 404 (not submitted) — never 401.

        Uses user_client_no_db because GET /exit-survey/me hits the DB directly
        (no intermediate service mock). The no_db fixture overrides get_session
        so no real PostgreSQL connection is needed in the API test tier.
        """
        resp = await user_client_no_db.get(f"{BASE}/exit-survey/me")
        assert resp.status_code != 401
        assert resp.status_code in (200, 404)
