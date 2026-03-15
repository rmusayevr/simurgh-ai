"""Phase 7 — API: Debate endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

BASE = "/api/v1/debates"
PROP_ID = 1
DEBATE_UUID = str(uuid4())


def _session():
    s = MagicMock()
    s.id = DEBATE_UUID
    s.proposal_id = PROP_ID
    s.debate_history = []
    s.turns = []
    s.final_consensus_proposal = None
    s.consensus_reached = False
    s.consensus_type = None
    s.total_turns = 0
    s.duration_seconds = 0.0
    s.conflict_density = 0.0
    s.legacy_keeper_consistency = 0.0
    s.innovator_consistency = 0.0
    s.mediator_consistency = 0.0
    s.overall_persona_consistency = 0.0
    s.started_at = datetime(2024, 1, 1)
    s.completed_at = None
    return s


class TestStartDebate:
    async def test_start_returns_200_or_201(self, user_client):
        from app.services.debate_service import DebateService

        with patch.object(
            DebateService, "conduct_debate", new=AsyncMock(return_value=_session())
        ):
            resp = await user_client.post(
                f"{BASE}/proposals/{PROP_ID}/start_debate",
                json={"document_ids": [], "focus_areas": []},
            )
        assert resp.status_code in (200, 201)

    async def test_start_proposal_not_found_returns_404(self, user_client):
        from app.services.debate_service import DebateService
        from app.core.exceptions import NotFoundException

        with patch.object(
            DebateService,
            "conduct_debate",
            new=AsyncMock(side_effect=NotFoundException("nf")),
        ):
            resp = await user_client.post(
                f"{BASE}/proposals/9999/start_debate",
                json={"document_ids": [], "focus_areas": []},
            )
        assert resp.status_code == 404

    async def test_start_requires_auth(self, client):
        resp = await client.post(
            f"{BASE}/proposals/{PROP_ID}/start_debate",
            json={"document_ids": [], "focus_areas": []},
        )
        assert resp.status_code == 401


class TestGetDebate:
    async def test_get_returns_200(self, user_client):
        from app.services.debate_service import DebateService

        with patch.object(
            DebateService, "get_debate_by_id", new=AsyncMock(return_value=_session())
        ):
            resp = await user_client.get(f"{BASE}/{DEBATE_UUID}")
        assert resp.status_code == 200

    async def test_get_requires_auth(self, client):
        assert (await client.get(f"{BASE}/{DEBATE_UUID}")).status_code == 401


class TestGetDebateTurns:
    async def test_turns_returns_200(self, user_client):
        from app.services.debate_service import DebateService

        with patch.object(
            DebateService, "get_debate_turns", new=AsyncMock(return_value=[])
        ):
            resp = await user_client.get(f"{BASE}/{DEBATE_UUID}/turns")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_turns_requires_auth(self, client):
        assert (await client.get(f"{BASE}/{DEBATE_UUID}/turns")).status_code == 401


class TestGetDebateMetrics:
    async def test_metrics_returns_200(self, user_client):
        from app.services.debate_service import DebateService

        with patch.object(
            DebateService, "get_debate_by_id", new=AsyncMock(return_value=_session())
        ):
            resp = await user_client.get(f"{BASE}/{DEBATE_UUID}/metrics")
        assert resp.status_code == 200

    async def test_metrics_requires_auth(self, client):
        assert (await client.get(f"{BASE}/{DEBATE_UUID}/metrics")).status_code == 401
