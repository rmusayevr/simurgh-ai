"""Phase 7 - API: Experiment data endpoints.

Covers all 10 endpoints in experiment_data.py:
  GET  /overview
  GET  /participants
  GET  /participants/{id}
  GET  /questionnaires
  GET  /debates
  GET  /exit-surveys
  GET  /rq-summary
  DELETE /reset
  DELETE /participants/{id}
  PATCH  /participants/{id}/invalidate

All tests use superuser_client (router requires get_current_superuser).
DB is mocked via get_session override — no real PostgreSQL needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from httpx import AsyncClient, ASGITransport

from app.models.exit_survey import ExitSurvey, PreferredSystem, FatigueLevel
from app.models.participant import Participant, ExperienceLevel, ConditionOrder
from app.models.questionnaire import QuestionnaireResponse, ExperimentCondition
from app.models.user import User, UserRole
from app.core.security import hash_password
from tests.fixtures.debates import build_complete_debate

BASE = "/api/v1/experiment-data"

# ── Shared factories ──────────────────────────────────────────────────────────

NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _make_participant(
    id: int = 1, user_id: int = 1, completed: bool = False
) -> Participant:
    return Participant(
        id=id,
        user_id=user_id,
        experience_level=ExperienceLevel.SENIOR,
        years_experience=5,
        familiarity_with_ai=4,
        consent_given=True,
        consent_timestamp=NOW,
        assigned_condition_order=ConditionOrder.BASELINE_FIRST,
        created_at=NOW,
        completed_at=NOW if completed else None,
    )


def _make_questionnaire(
    participant_id: int = 1,
    condition: ExperimentCondition = ExperimentCondition.BASELINE,
    is_valid: bool = True,
) -> QuestionnaireResponse:
    return QuestionnaireResponse(
        id=uuid4(),
        participant_id=participant_id,
        scenario_id=1,
        condition=condition,
        condition_order="baseline_first",
        order_in_session=1,
        session_id="sess-001",
        trust_overall=5,
        risk_awareness=5,
        technical_soundness=5,
        balance=5,
        actionability=5,
        completeness=5,
        strengths="Good proposal.",
        concerns="Minor issues.",
        trust_reasoning="Well structured.",
        time_to_complete_seconds=90,
        is_valid=is_valid,
        quality_note=None,
        submitted_at=NOW,
    )


def _make_exit_survey(participant_id: int = 1) -> ExitSurvey:
    return ExitSurvey(
        id=uuid4(),
        participant_id=participant_id,
        preferred_system=PreferredSystem.FIRST,
        preferred_system_actual="baseline",
        preference_reasoning="Felt clearer.",
        interface_rating=5,
        experienced_fatigue=FatigueLevel.A_LITTLE,
        submitted_at=NOW,
    )


def _make_superuser() -> User:
    return User(
        id=999,
        email="super@example.com",
        hashed_password=hash_password("SuperPass123!"),
        full_name="Super User",
        role=UserRole.ADMIN,
        is_active=True,
        is_superuser=True,
        email_verified=True,
        terms_accepted=True,
    )


# ── Session mock factory ──────────────────────────────────────────────────────


def _mock_session(exec_side_effects: list | None = None) -> AsyncMock:
    """
    AsyncMock session whose .exec() calls return values in sequence.

      int   → .one() returns that int   (COUNT queries)
      list  → .all() returns that list  (SELECT * queries)
      None  → .first() returns None
    """
    session = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    if exec_side_effects is None:

        def _default(*a, **kw):
            r = MagicMock()
            r.one = MagicMock(return_value=0)
            r.all = MagicMock(return_value=[])
            r.first = MagicMock(return_value=None)
            return r

        session.exec = AsyncMock(side_effect=lambda *a, **kw: _default())
        return session

    results = []
    for effect in exec_side_effects:
        r = MagicMock()
        if isinstance(effect, int):
            r.one = MagicMock(return_value=effect)
            r.all = MagicMock(return_value=[])
            r.first = MagicMock(return_value=None)
        elif isinstance(effect, list):
            r.all = MagicMock(return_value=effect)
            r.one = MagicMock(return_value=len(effect))
            r.first = MagicMock(return_value=effect[0] if effect else None)
        else:
            r.first = MagicMock(return_value=effect)
            r.all = MagicMock(return_value=[effect] if effect else [])
            r.one = MagicMock(return_value=1 if effect else 0)
        results.append(r)

    session.exec = AsyncMock(side_effect=results)
    return session


# ── Client builder ────────────────────────────────────────────────────────────


def _client(session: AsyncMock):
    """Return an AsyncClient context manager with superuser + mock session."""
    from app.main import app
    from app.api.v1.dependencies import get_current_superuser, get_session

    stub = _make_superuser()
    app.dependency_overrides[get_current_superuser] = lambda: stub
    app.dependency_overrides[get_session] = lambda: session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), app


async def _cleanup(app):
    from app.api.v1.dependencies import get_current_superuser, get_session

    app.dependency_overrides.pop(get_current_superuser, None)
    app.dependency_overrides.pop(get_session, None)


# ── Auth guards ───────────────────────────────────────────────────────────────


class TestExperimentDataAuthGuards:
    async def test_get_overview_without_auth_returns_401(
        self, unauthed_client: AsyncClient
    ):
        resp = await unauthed_client.get(f"{BASE}/overview")
        assert resp.status_code == 401

    async def test_get_overview_with_regular_user_returns_403(
        self, user_client: AsyncClient
    ):
        resp = await user_client.get(f"{BASE}/overview")
        assert resp.status_code == 403

    async def test_get_participants_without_auth_returns_401(
        self, unauthed_client: AsyncClient
    ):
        resp = await unauthed_client.get(f"{BASE}/participants")
        assert resp.status_code == 401

    async def test_get_rq_summary_without_auth_returns_401(
        self, unauthed_client: AsyncClient
    ):
        resp = await unauthed_client.get(f"{BASE}/rq-summary")
        assert resp.status_code == 401

    async def test_delete_reset_without_auth_returns_401(
        self, unauthed_client: AsyncClient
    ):
        resp = await unauthed_client.delete(
            f"{BASE}/reset", params={"confirm": "CONFIRM_RESET"}
        )
        assert resp.status_code == 401

    async def test_delete_participant_without_auth_returns_401(
        self, unauthed_client: AsyncClient
    ):
        resp = await unauthed_client.delete(f"{BASE}/participants/1")
        assert resp.status_code == 401

    async def test_patch_invalidate_without_auth_returns_401(
        self, unauthed_client: AsyncClient
    ):
        resp = await unauthed_client.patch(
            f"{BASE}/participants/1/invalidate",
            params={"reason": "spam response"},
        )
        assert resp.status_code == 401

    async def test_get_export_with_auth_returns_non_401(
        self, authed_client: AsyncClient
    ):
        resp = await authed_client.get(f"{BASE}/overview")
        assert resp.status_code != 401


# ── GET /overview ─────────────────────────────────────────────────────────────


class TestGetOverview:
    async def test_returns_200_with_empty_db(self):
        ac, app = _client(_mock_session())
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/overview")
            assert resp.status_code == 200
        finally:
            await _cleanup(app)

    async def test_overview_shape(self):
        ac, app = _client(_mock_session())
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/overview")
            data = resp.json()
            for key in (
                "participants",
                "questionnaires",
                "debates",
                "exit_surveys",
                "rq2_persona_codings",
            ):
                assert key in data
        finally:
            await _cleanup(app)

    async def test_overview_counts_with_data(self):
        # 10 COUNT queries then 2 SELECT * queries
        effects = [5, 3, 8, 6, 4, 2, 3, 10, 3, 2, [], []]
        ac, app = _client(_mock_session(effects))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/overview")
            data = resp.json()
            assert data["participants"]["total"] == 5
            assert data["participants"]["completed"] == 3
            assert data["questionnaires"]["total"] == 8
            assert data["debates"]["total"] == 4
        finally:
            await _cleanup(app)

    async def test_overview_zero_division_safe(self):
        ac, app = _client(_mock_session())
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/overview")
            data = resp.json()
            # With zero participants, percentages should be 0 (not division by zero)
            assert data["participants"]["completion_rate_pct"] == 0
        finally:
            await _cleanup(app)


# ── GET /participants ─────────────────────────────────────────────────────────


class TestListParticipants:
    async def test_returns_200_empty(self):
        # 4 SELECT queries: participants, questionnaires, surveys, users
        ac, app = _client(_mock_session([[], [], [], []]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/participants")
            assert resp.status_code == 200
            assert resp.json()["total"] == 0
        finally:
            await _cleanup(app)

    async def test_returns_participant_with_user(self):
        p = _make_participant(id=1, user_id=10)
        u = User(
            id=10,
            email="p@example.com",
            hashed_password="x",
            full_name="Participant One",
            role=UserRole.USER,
            is_active=True,
            is_superuser=False,
            email_verified=True,
            terms_accepted=True,
        )
        ac, app = _client(_mock_session([[p], [], [], [u]]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/participants")
            data = resp.json()
            assert data["total"] == 1
            assert data["participants"][0]["participant_id"] == 1
            assert data["participants"][0]["user"]["email"] == "p@example.com"
        finally:
            await _cleanup(app)

    async def test_completed_only_filter_accepted(self):
        ac, app = _client(_mock_session([[], [], [], []]))
        try:
            async with ac as c:
                resp = await c.get(
                    f"{BASE}/participants", params={"completed_only": "true"}
                )
            assert resp.status_code == 200
        finally:
            await _cleanup(app)

    async def test_condition_order_filter_accepted(self):
        ac, app = _client(_mock_session([[], [], [], []]))
        try:
            async with ac as c:
                resp = await c.get(
                    f"{BASE}/participants",
                    params={"condition_order": "baseline_first"},
                )
            assert resp.status_code == 200
        finally:
            await _cleanup(app)


# ── GET /participants/{id} ────────────────────────────────────────────────────


class TestGetParticipantDetail:
    async def test_returns_404_when_participant_missing(self):
        session = _mock_session()
        session.get = AsyncMock(return_value=None)
        ac, app = _client(session)
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/participants/999")
            assert resp.status_code == 404
        finally:
            await _cleanup(app)

    async def test_returns_200_with_existing_participant(self):
        p = _make_participant(id=1, user_id=10)
        u = User(
            id=10,
            email="detail@example.com",
            hashed_password="x",
            full_name="Detail User",
            role=UserRole.USER,
            is_active=True,
            is_superuser=False,
            email_verified=True,
            terms_accepted=True,
        )
        session = _mock_session()
        call_count = 0

        async def mock_get(model, pk):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return p
            return u

        session.get = mock_get
        q_r = MagicMock()
        q_r.all = MagicMock(return_value=[])
        s_r = MagicMock()
        s_r.first = MagicMock(return_value=None)
        session.exec = AsyncMock(side_effect=[q_r, s_r])
        ac, app = _client(session)
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/participants/1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["participant_id"] == 1
            assert data["user"]["email"] == "detail@example.com"
            assert "questionnaires" in data
            assert "exit_survey" in data
        finally:
            await _cleanup(app)

    async def test_returns_both_condition_questionnaires(self):
        p = _make_participant(id=1, user_id=10)
        u = User(
            id=10,
            email="both@example.com",
            hashed_password="x",
            full_name="Both User",
            role=UserRole.USER,
            is_active=True,
            is_superuser=False,
            email_verified=True,
            terms_accepted=True,
        )
        q_b = _make_questionnaire(
            participant_id=1, condition=ExperimentCondition.BASELINE
        )
        q_m = _make_questionnaire(
            participant_id=1, condition=ExperimentCondition.MULTIAGENT
        )
        session = _mock_session()
        call_count = 0

        async def mock_get(model, pk):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return p
            return u

        session.get = mock_get
        q_r = MagicMock()
        q_r.all = MagicMock(return_value=[q_b, q_m])
        s_r = MagicMock()
        s_r.first = MagicMock(return_value=None)
        session.exec = AsyncMock(side_effect=[q_r, s_r])
        ac, app = _client(session)
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/participants/1")
            qs = resp.json()["questionnaires"]
            assert len(qs["baseline"]) == 1
            assert len(qs["multiagent"]) == 1
        finally:
            await _cleanup(app)


# ── GET /questionnaires ───────────────────────────────────────────────────────


class TestListQuestionnaireResponses:
    async def test_returns_200_empty(self):
        ac, app = _client(_mock_session([[]]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/questionnaires")
            assert resp.status_code == 200
            assert resp.json()["total"] == 0
        finally:
            await _cleanup(app)

    async def test_returns_questionnaire_data(self):
        q = _make_questionnaire(condition=ExperimentCondition.BASELINE)
        ac, app = _client(_mock_session([[q]]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/questionnaires")
            data = resp.json()
            assert data["total"] == 1
            assert data["responses"][0]["condition"] == "BASELINE"
        finally:
            await _cleanup(app)

    async def test_condition_filter_accepted(self):
        ac, app = _client(_mock_session([[]]))
        try:
            async with ac as c:
                resp = await c.get(
                    f"{BASE}/questionnaires", params={"condition": "BASELINE"}
                )
            assert resp.status_code == 200
        finally:
            await _cleanup(app)

    async def test_valid_only_false_accepted(self):
        ac, app = _client(_mock_session([[]]))
        try:
            async with ac as c:
                resp = await c.get(
                    f"{BASE}/questionnaires", params={"valid_only": "false"}
                )
            assert resp.status_code == 200
        finally:
            await _cleanup(app)

    async def test_aggregate_keys_present(self):
        ac, app = _client(_mock_session([[]]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/questionnaires")
            assert "by_condition" in resp.json()
            assert "baseline" in resp.json()["by_condition"]
            assert "multiagent" in resp.json()["by_condition"]
        finally:
            await _cleanup(app)


# ── GET /debates ──────────────────────────────────────────────────────────────


class TestListDebateSessions:
    async def test_returns_200_empty(self):
        ac, app = _client(_mock_session([[]]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/debates")
            assert resp.status_code == 200
            assert resp.json()["total"] == 0
        finally:
            await _cleanup(app)

    async def test_returns_debate_with_metrics(self):
        debate = build_complete_debate(proposal_id=1)
        ac, app = _client(_mock_session([[debate]]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/debates")
            data = resp.json()
            assert data["total"] == 1
            assert data["debates"][0]["consensus"]["reached"] is True
            assert "metrics" in data["debates"][0]
        finally:
            await _cleanup(app)

    async def test_include_turns_false_omits_history(self):
        debate = build_complete_debate()
        ac, app = _client(_mock_session([[debate]]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/debates", params={"include_turns": "false"})
            assert "debate_history" not in resp.json()["debates"][0]
        finally:
            await _cleanup(app)

    async def test_include_turns_true_includes_history(self):
        debate = build_complete_debate()
        ac, app = _client(_mock_session([[debate]]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/debates", params={"include_turns": "true"})
            assert "debate_history" in resp.json()["debates"][0]
        finally:
            await _cleanup(app)

    async def test_consensus_rate_zero_when_no_debates(self):
        ac, app = _client(_mock_session([[]]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/debates")
            assert resp.json()["consensus_rate_pct"] == 0
        finally:
            await _cleanup(app)


# ── GET /exit-surveys ─────────────────────────────────────────────────────────


class TestListExitSurveys:
    async def test_returns_200_empty(self):
        ac, app = _client(_mock_session([[], []]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/exit-surveys")
            assert resp.status_code == 200
            assert resp.json()["total"] == 0
        finally:
            await _cleanup(app)

    async def test_returns_survey_data(self):
        survey = _make_exit_survey(participant_id=1)
        p = _make_participant(id=1)
        ac, app = _client(_mock_session([[survey], [p]]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/exit-surveys")
            data = resp.json()
            assert data["total"] == 1
            assert data["surveys"][0]["participant_id"] == 1
            assert data["surveys"][0]["preference"]["actual"] == "baseline"
        finally:
            await _cleanup(app)

    async def test_preference_counts_in_response(self):
        ac, app = _client(_mock_session([[], []]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/exit-surveys")
            assert "preference_counts" in resp.json()
        finally:
            await _cleanup(app)


# ── GET /rq-summary ───────────────────────────────────────────────────────────


class TestGetRqSummary:
    async def test_returns_200(self):
        # 4 queries: questionnaires, codings, debates, ProposalVariation
        ac, app = _client(_mock_session([[], [], [], []]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/rq-summary")
            assert resp.status_code == 200
        finally:
            await _cleanup(app)

    async def test_rq_summary_shape(self):
        ac, app = _client(_mock_session([[], [], [], []]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/rq-summary")
            data = resp.json()
            for key in (
                "rq1_trust_and_quality",
                "rq2_persona_consistency",
                "rq3_consensus_efficiency",
                "generated_at",
            ):
                assert key in data
        finally:
            await _cleanup(app)

    async def test_rq1_contains_cohen_d(self):
        ac, app = _client(_mock_session([[], [], [], []]))
        try:
            async with ac as c:
                resp = await c.get(f"{BASE}/rq-summary")
            rq1 = resp.json()["rq1_trust_and_quality"]
            assert "cohen_d" in rq1["composite_mean_score"]
        finally:
            await _cleanup(app)


# ── DELETE /reset ─────────────────────────────────────────────────────────────


class TestResetExperimentData:
    async def test_reset_wrong_confirm_returns_400(self):
        ac, app = _client(_mock_session())
        try:
            async with ac as c:
                resp = await c.delete(f"{BASE}/reset", params={"confirm": "WRONG"})
            assert resp.status_code == 400
        finally:
            await _cleanup(app)

    async def test_reset_missing_confirm_returns_422(self):
        ac, app = _client(_mock_session())
        try:
            async with ac as c:
                resp = await c.delete(f"{BASE}/reset")
            assert resp.status_code == 422
        finally:
            await _cleanup(app)

    async def test_reset_correct_confirm_returns_200(self):
        # 5 COUNT queries + 5 SELECT * for delete loops
        effects = [0, 0, 0, 0, 0, [], [], [], [], []]
        ac, app = _client(_mock_session(effects))
        try:
            async with ac as c:
                resp = await c.delete(
                    f"{BASE}/reset", params={"confirm": "CONFIRM_RESET"}
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "records_deleted" in data
        finally:
            await _cleanup(app)

    async def test_reset_keep_participants_flag(self):
        effects = [0, 0, 0, 0, 0, [], [], [], []]
        ac, app = _client(_mock_session(effects))
        try:
            async with ac as c:
                resp = await c.delete(
                    f"{BASE}/reset",
                    params={"confirm": "CONFIRM_RESET", "keep_participants": "true"},
                )
            assert resp.status_code == 200
            assert resp.json()["keep_participants"] is True
        finally:
            await _cleanup(app)

    async def test_reset_includes_requested_by_email(self):
        effects = [0, 0, 0, 0, 0, [], [], [], [], []]
        ac, app = _client(_mock_session(effects))
        try:
            async with ac as c:
                resp = await c.delete(
                    f"{BASE}/reset", params={"confirm": "CONFIRM_RESET"}
                )
            assert resp.json()["requested_by"] == "super@example.com"
        finally:
            await _cleanup(app)


# ── DELETE /participants/{id} ──────────────────────────────────────────────────


class TestDeleteParticipant:
    async def test_returns_404_when_not_found(self):
        session = _mock_session()
        session.get = AsyncMock(return_value=None)
        ac, app = _client(session)
        try:
            async with ac as c:
                resp = await c.delete(f"{BASE}/participants/999")
            assert resp.status_code == 404
        finally:
            await _cleanup(app)

    async def test_returns_200_on_successful_delete(self):
        p = _make_participant(id=1, user_id=10)
        u = User(
            id=10,
            email="del@example.com",
            hashed_password="x",
            full_name="Delete Me",
            role=UserRole.USER,
            is_active=True,
            is_superuser=False,
            email_verified=True,
            terms_accepted=True,
        )
        session = _mock_session()
        call_count = 0

        async def mock_get(model, pk):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return p
            return u

        session.get = mock_get
        qr_r = MagicMock()
        qr_r.all = MagicMock(return_value=[])
        sv_r = MagicMock()
        sv_r.first = MagicMock(return_value=None)
        db_r = MagicMock()
        db_r.all = MagicMock(return_value=[])
        session.exec = AsyncMock(side_effect=[qr_r, sv_r, db_r])
        ac, app = _client(session)
        try:
            async with ac as c:
                resp = await c.delete(f"{BASE}/participants/1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["deleted_participant_id"] == 1
        finally:
            await _cleanup(app)

    async def test_counts_deleted_questionnaires(self):
        p = _make_participant(id=1, user_id=10)
        q1 = _make_questionnaire(participant_id=1)
        q2 = _make_questionnaire(
            participant_id=1, condition=ExperimentCondition.MULTIAGENT
        )
        session = _mock_session()
        call_count = 0

        async def mock_get(model, pk):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return p
            return None

        session.get = mock_get
        qr_r = MagicMock()
        qr_r.all = MagicMock(return_value=[q1, q2])
        sv_r = MagicMock()
        sv_r.first = MagicMock(return_value=None)
        db_r = MagicMock()
        db_r.all = MagicMock(return_value=[])
        session.exec = AsyncMock(side_effect=[qr_r, sv_r, db_r])
        ac, app = _client(session)
        try:
            async with ac as c:
                resp = await c.delete(f"{BASE}/participants/1")
            assert resp.status_code == 200
            assert resp.json()["success"] is True
        finally:
            await _cleanup(app)


# ── PATCH /participants/{id}/invalidate ────────────────────────────────────────


class TestInvalidateParticipant:
    async def test_returns_404_when_not_found(self):
        session = _mock_session()
        session.get = AsyncMock(return_value=None)
        ac, app = _client(session)
        try:
            async with ac as c:
                resp = await c.patch(
                    f"{BASE}/participants/999/invalidate",
                    params={"reason": "test invalidation reason"},
                )
            assert resp.status_code == 404
        finally:
            await _cleanup(app)

    async def test_returns_400_when_no_questionnaires(self):
        p = _make_participant(id=1)
        session = _mock_session()
        session.get = AsyncMock(return_value=p)
        qs_r = MagicMock()
        qs_r.all = MagicMock(return_value=[])
        session.exec = AsyncMock(return_value=qs_r)
        ac, app = _client(session)
        try:
            async with ac as c:
                resp = await c.patch(
                    f"{BASE}/participants/1/invalidate",
                    params={"reason": "test invalidation reason"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["invalidated_count"] == 0
        finally:
            await _cleanup(app)

    async def test_invalidates_all_responses_returns_200(self):
        p = _make_participant(id=1)
        q1 = _make_questionnaire(participant_id=1, is_valid=True)
        q2 = _make_questionnaire(
            participant_id=1, condition=ExperimentCondition.MULTIAGENT, is_valid=True
        )
        session = _mock_session()
        session.get = AsyncMock(return_value=p)
        qs_r = MagicMock()
        qs_r.all = MagicMock(return_value=[q1, q2])
        session.exec = AsyncMock(return_value=qs_r)
        ac, app = _client(session)
        try:
            async with ac as c:
                resp = await c.patch(
                    f"{BASE}/participants/1/invalidate",
                    params={"reason": "participant showed signs of disengagement"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["invalidated_count"] == 2
        finally:
            await _cleanup(app)


# ── GET /debates ───────────────────────────────────────────────────────────────
