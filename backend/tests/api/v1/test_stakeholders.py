"""Phase 7 — API: Stakeholder endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

BASE = "/api/v1/stakeholders"
PID = 1
SID = 10


def _sh(id=SID, project_id=PID):
    s = MagicMock()
    s.id = id
    s.name = "Alice"
    s.role = "CTO"
    s.project_id = project_id
    s.influence = "HIGH"
    s.interest = "HIGH"
    s.sentiment = "NEUTRAL"
    s.strategic_plan = None
    s.notes = None
    s.concerns = None
    s.motivations = None
    s.department = None
    s.email = None
    s.approval_role = None
    s.notify_on_approval_needed = False
    s.created_at = "2024-01-01T00:00:00"
    s.updated_at = "2024-01-01T00:00:00"
    return s


def _payload(**kw):
    d = {
        "name": "Alice",
        "role": "CTO",
        "influence": "HIGH",
        "interest": "HIGH",
        "sentiment": "NEUTRAL",
    }
    d.update(kw)
    return d


class TestCreateStakeholder:
    async def test_create_returns_201(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        with patch.object(
            StakeholderService, "create_stakeholder", new=AsyncMock(return_value=_sh())
        ):
            resp = await user_client.post(f"{BASE}/project/{PID}", json=_payload())
        assert resp.status_code == 201

    async def test_create_invalid_influence_returns_422(self, user_client):
        resp = await user_client.post(
            f"{BASE}/project/{PID}", json=_payload(influence="ULTRA")
        )
        assert resp.status_code == 422

    async def test_create_requires_auth(self, client):
        assert (
            await client.post(f"{BASE}/project/{PID}", json=_payload())
        ).status_code == 401


class TestListStakeholders:
    async def test_list_returns_200(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        with patch.object(
            StakeholderService,
            "get_project_stakeholders",
            new=AsyncMock(return_value=[_sh()]),
        ):
            resp = await user_client.get(f"{BASE}/project/{PID}")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_requires_auth(self, client):
        assert (await client.get(f"{BASE}/project/{PID}")).status_code == 401


class TestGetStakeholder:
    async def test_get_returns_200(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        with patch.object(
            StakeholderService, "get_by_id", new=AsyncMock(return_value=_sh())
        ):
            resp = await user_client.get(f"{BASE}/{SID}")
        assert resp.status_code == 200

    async def test_get_nonexistent_returns_404(self, user_client):
        from app.services.stakeholder_service import StakeholderService
        from app.core.exceptions import NotFoundException

        with patch.object(
            StakeholderService,
            "get_by_id",
            new=AsyncMock(side_effect=NotFoundException("nf")),
        ):
            resp = await user_client.get(f"{BASE}/9999")
        assert resp.status_code == 404

    async def test_get_wrong_project_returns_403(self, user_client):
        from app.services.stakeholder_service import StakeholderService
        from app.core.exceptions import ForbiddenException

        with patch.object(
            StakeholderService,
            "get_by_id",
            new=AsyncMock(side_effect=ForbiddenException("no access")),
        ):
            resp = await user_client.get(f"{BASE}/{SID}")
        assert resp.status_code == 403

    async def test_get_requires_auth(self, client):
        assert (await client.get(f"{BASE}/{SID}")).status_code == 401


class TestUpdateStakeholder:
    async def test_update_returns_200(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        with patch.object(
            StakeholderService, "update_stakeholder", new=AsyncMock(return_value=_sh())
        ):
            resp = await user_client.patch(f"{BASE}/{SID}", json={"influence": "HIGH"})
        assert resp.status_code == 200

    async def test_update_requires_auth(self, client):
        assert (
            await client.patch(f"{BASE}/{SID}", json={"influence": "HIGH"})
        ).status_code == 401


class TestDeleteStakeholder:
    async def test_delete_returns_204(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        with patch.object(
            StakeholderService, "delete_stakeholder", new=AsyncMock(return_value=None)
        ):
            resp = await user_client.delete(f"{BASE}/{SID}")
        assert resp.status_code == 204

    async def test_delete_nonexistent_returns_404(self, user_client):
        from app.services.stakeholder_service import StakeholderService
        from app.core.exceptions import NotFoundException

        with patch.object(
            StakeholderService,
            "delete_stakeholder",
            new=AsyncMock(side_effect=NotFoundException("nf")),
        ):
            resp = await user_client.delete(f"{BASE}/9999")
        assert resp.status_code == 404

    async def test_delete_requires_auth(self, client):
        assert (await client.delete(f"{BASE}/{SID}")).status_code == 401


class TestStakeholderMatrix:
    async def test_matrix_returns_200(self, user_client):
        from app.services.stakeholder_service import StakeholderService

        matrix = {
            "key_players": [],
            "keep_satisfied": [],
            "keep_informed": [],
            "monitor": [],
        }
        with patch.object(
            StakeholderService,
            "get_stakeholder_matrix",
            new=AsyncMock(return_value=matrix),
        ):
            resp = await user_client.get(f"{BASE}/project/{PID}/matrix")
        assert resp.status_code == 200

    async def test_matrix_requires_auth(self, client):
        assert (await client.get(f"{BASE}/project/{PID}/matrix")).status_code == 401
