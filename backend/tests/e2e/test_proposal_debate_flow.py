"""
E2E tests — Proposal + Debate flow (Phase 8).

Fix notes vs original failures:
    6. RuntimeError: AI failure (test_start_debate_error_returns_4xx_or_5xx)
       → start_debate endpoint now wraps unexpected exceptions in a 500 HTTPException.
         The test raises RuntimeError; this must now return 500 (not crash).

    7. ResponseValidationError (test_get_debate_returns_200)
    8. ResponseValidationError (test_timeout_debate_not_an_error)
       → DebateSessionDetail.turns was a required List[DebateTurnRead] but
         DebateSession stores turns in JSONB (debate_history), not a relationship.
         Fixed by making turns optional (default=[]) and adding from_session()
         classmethod that maps debate_history → turns.
         The endpoint now calls DebateSessionDetail.from_session(debate).
"""

import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime
from httpx import AsyncClient, ASGITransport


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_app():
    from app.main import app

    return app


def _stub_user(user_id=1, is_superuser=False):
    from app.models.user import User, UserRole
    from app.core.security import hash_password

    return User(
        id=user_id,
        email="user@example.com",
        hashed_password=hash_password("Password123!"),
        full_name="Test User",
        role=UserRole.ADMIN if is_superuser else UserRole.USER,
        is_active=True,
        is_superuser=is_superuser,
        email_verified=True,
        terms_accepted=True,
    )


def _make_debate_session(debate_id=None, with_turns=False):
    """Build a minimal DebateSession-like mock that serialises cleanly."""
    s = MagicMock()
    s.id = debate_id or uuid4()
    s.proposal_id = 1
    s.debate_history = (
        [
            {
                "turn_number": 1,
                "persona": "legacy_keeper",
                "response": "This is the legacy keeper response.",
                "timestamp": datetime.utcnow().isoformat(),
                "sentiment": "neutral",
                "key_points": ["stability"],
                "quality_attributes_mentioned": [],
                "bias_alignment_score": 0.8,
            }
        ]
        if with_turns
        else []
    )
    s.turns = s.debate_history  # alias used by some serialisation paths
    s.final_consensus_proposal = None
    s.consensus_reached = False
    s.consensus_type = None
    s.consensus_confidence = None
    s.total_turns = len(s.debate_history)
    s.duration_seconds = 12.5
    s.conflict_density = 0.0
    s.legacy_keeper_consistency = 0.9
    s.innovator_consistency = 0.85
    s.mediator_consistency = 0.88
    s.overall_persona_consistency = 0.88
    s.started_at = datetime.utcnow()
    s.completed_at = None
    # Support __dict__ access used by from_session()
    s.__dict__.update(
        {
            "id": s.id,
            "proposal_id": s.proposal_id,
            "debate_history": s.debate_history,
            "final_consensus_proposal": s.final_consensus_proposal,
            "consensus_reached": s.consensus_reached,
            "consensus_type": s.consensus_type,
            "consensus_confidence": s.consensus_confidence,
            "total_turns": s.total_turns,
            "duration_seconds": s.duration_seconds,
            "conflict_density": s.conflict_density,
            "legacy_keeper_consistency": s.legacy_keeper_consistency,
            "innovator_consistency": s.innovator_consistency,
            "mediator_consistency": s.mediator_consistency,
            "overall_persona_consistency": s.overall_persona_consistency,
            "started_at": s.started_at,
            "completed_at": s.completed_at,
        }
    )
    return s


# ── Function-scoped fixtures ──────────────────────────────────────────────────


@pytest_asyncio.fixture
async def anon_client():
    app = _get_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def user_client():
    app = _get_app()
    from app.api.v1.dependencies import get_current_user

    stub = _stub_user()
    app.dependency_overrides[get_current_user] = lambda: stub
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_current_user, None)


DEBATE_ID = str(uuid4())
PROP_ID = 1


# ── Test classes ──────────────────────────────────────────────────────────────


class TestDebateInitiation:
    async def test_start_debate_returns_200_or_201(self, user_client):
        from app.services.debate_service import DebateService

        session = _make_debate_session()
        with patch.object(
            DebateService, "conduct_debate", new=AsyncMock(return_value=session)
        ):
            resp = await user_client.post(
                f"/api/v1/debates/proposals/{PROP_ID}/start_debate",
                json={"document_ids": [], "focus_areas": []},
            )
        assert resp.status_code in (200, 201)

    async def test_start_debate_error_returns_4xx_or_5xx(self, user_client):
        """
        Fix #6: start_debate now wraps unexpected exceptions in a 500 HTTPException.
        Previously a bare RuntimeError propagated unhandled; now returns 500.
        """
        from app.services.debate_service import DebateService

        with patch.object(
            DebateService,
            "conduct_debate",
            new=AsyncMock(side_effect=RuntimeError("AI failure")),
        ):
            resp = await user_client.post(
                f"/api/v1/debates/proposals/{PROP_ID}/start_debate",
                json={"document_ids": [], "focus_areas": []},
            )
        assert resp.status_code in range(400, 600), (
            f"Expected 4xx/5xx but got {resp.status_code}"
        )

    async def test_start_debate_requires_auth(self, anon_client):
        resp = await anon_client.post(
            f"/api/v1/debates/proposals/{PROP_ID}/start_debate",
            json={"document_ids": [], "focus_areas": []},
        )
        assert resp.status_code == 401


class TestDebateRetrieval:
    async def test_get_debate_returns_200(self, user_client):
        """
        Fix #7: DebateSessionDetail.turns is now optional (default=[]) and
        the endpoint calls DebateSessionDetail.from_session() which maps
        debate_history → turns. No ResponseValidationError.
        """
        from app.services.debate_service import DebateService

        session = _make_debate_session(debate_id=uuid4(), with_turns=True)
        with patch.object(
            DebateService,
            "get_debate_by_id",
            new=AsyncMock(return_value=session),
        ):
            resp = await user_client.get(f"/api/v1/debates/{session.id}")
        assert resp.status_code == 200

    async def test_get_debate_turns_returns_list(self, user_client):
        from app.services.debate_service import DebateService

        with patch.object(
            DebateService,
            "get_debate_turns",
            new=AsyncMock(return_value=[]),
        ):
            resp = await user_client.get(f"/api/v1/debates/{DEBATE_ID}/turns")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_debate_requires_auth(self, anon_client):
        resp = await anon_client.get(f"/api/v1/debates/{DEBATE_ID}")
        assert resp.status_code == 401


class TestDebateMetrics:
    async def test_timeout_debate_not_an_error(self, user_client):
        """
        Fix #8: same DebateSessionDetail.turns fix as #7. A debate that
        timed out (no consensus, 0 turns) must still serialise without error.
        """
        from app.services.debate_service import DebateService

        # Simulate a timed-out debate: empty history, no consensus
        session = _make_debate_session(debate_id=uuid4(), with_turns=False)
        with patch.object(
            DebateService,
            "get_debate_by_id",
            new=AsyncMock(return_value=session),
        ):
            resp = await user_client.get(f"/api/v1/debates/{session.id}/metrics")
        assert resp.status_code == 200

    async def test_metrics_requires_auth(self, anon_client):
        resp = await anon_client.get(f"/api/v1/debates/{DEBATE_ID}/metrics")
        assert resp.status_code == 401
