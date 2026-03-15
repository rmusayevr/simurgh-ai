"""Phase 7 — API: Experiments / participant registration endpoints."""

BASE = "/api/v1/experiments"


class TestRegisterParticipant:
    async def test_register_requires_auth(self, client):
        resp = await client.post(f"{BASE}/register", json={"consent_given": True})
        assert resp.status_code == 401

    async def test_register_without_consent_returns_422(self, user_client):
        """consent_given=False should fail schema validation."""
        resp = await user_client.post(f"{BASE}/register", json={"consent_given": False})
        assert resp.status_code == 422

    async def test_register_valid_payload_not_401(self, user_client):
        """With auth and valid payload, should not be 401."""
        resp = await user_client.post(
            f"{BASE}/register",
            json={
                "consent_given": True,
                "age_range": "25-34",
                "years_experience": 3,
                "role": "Engineer",
                "education_level": "Bachelor",
                "familiarity_with_ai": 4,
                "familiarity_with_architecture": 5,
            },
        )
        assert resp.status_code != 401


class TestGetParticipantMe:
    async def test_get_me_requires_auth(self, client):
        assert (await client.get(f"{BASE}/participant/me")).status_code == 401

    async def test_get_me_authenticated_not_401(self, user_client_no_db):
        resp = await user_client_no_db.get(f"{BASE}/participant/me")
        assert resp.status_code != 401
