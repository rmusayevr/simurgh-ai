"""
Unit tests for app/services/debate_service.py

Covers:
    TURN_ORDER constant
    DebateSession.add_turn           (model helper)
    DebateSession.complete()         (model helper)
    DebateSession.calculate_persona_consistency
    DebateService._calculate_conflict_density
    DebateService._calculate_persona_consistency
    DebateService._get_debate_history_from_session
    DebateService._get_debate_history       (async, DB read)
    DebateService._check_consensus          (AI call mocked)
    DebateService._get_rag_context          (vector service mocked)
    DebateService._execute_turn             (persona service mocked)
    DebateService._generate_final_proposal  (AI service mocked)
    DebateService.get_debate_by_id          (access control)
    DebateService.get_debates_by_proposal   (list, ordering)
    DebateService.get_debate_turns          (sorted)
    DebateService.conduct_debate            (full orchestration, error path)

DB calls and external AI services are mocked — no real PostgreSQL or Anthropic API.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from app.models.debate import DebateSession, ConsensusType
from app.models.proposal import AgentPersona, Proposal, ProposalStatus, ApprovalStatus
from app.models.user import UserRole
from app.core.exceptions import NotFoundException, DebateException
from tests.fixtures.debates import (
    build_debate_session,
    build_complete_debate,
    build_in_progress_debate,
)


# ── Shared helpers ─────────────────────────────────────────────────────────────

NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _make_proposal(id: int = 1, project_id: int = 10) -> Proposal:
    return Proposal(
        id=id,
        task_description="Migrate monolith to microservices",
        project_id=project_id,
        status=ProposalStatus.DRAFT,
        approval_status=ApprovalStatus.DRAFT,
        created_by_id=1,
    )


def _make_service(session=None):
    from app.services.debate_service import DebateService

    svc = DebateService.__new__(DebateService)
    svc.session = session or AsyncMock()
    svc.vector_service = AsyncMock()
    svc.persona_service = AsyncMock()
    return svc


def _make_db_session(get_return=None, exec_returns: list | None = None) -> AsyncMock:
    session = AsyncMock()
    session.get = AsyncMock(return_value=get_return)
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()

    if exec_returns is not None:
        results = []
        for val in exec_returns:
            r = MagicMock()
            if isinstance(val, list):
                r.all = MagicMock(return_value=val)
                r.first = MagicMock(return_value=val[0] if val else None)
            else:
                r.first = MagicMock(return_value=val)
                r.all = MagicMock(return_value=[val] if val else [])
            results.append(r)
        session.exec = AsyncMock(side_effect=results)
    else:
        default = MagicMock()
        default.first = MagicMock(return_value=None)
        default.all = MagicMock(return_value=[])
        session.exec = AsyncMock(return_value=default)

    return session


# ══════════════════════════════════════════════════════════════════
# TURN_ORDER constant
# ══════════════════════════════════════════════════════════════════


class TestTurnOrder:
    def test_first_turn_is_legacy_keeper(self):
        from app.services.debate_service import DebateService

        assert DebateService.TURN_ORDER[0] == AgentPersona.LEGACY_KEEPER

    def test_second_turn_is_innovator(self):
        from app.services.debate_service import DebateService

        assert DebateService.TURN_ORDER[1] == AgentPersona.INNOVATOR

    def test_third_turn_is_mediator(self):
        from app.services.debate_service import DebateService

        assert DebateService.TURN_ORDER[2] == AgentPersona.MEDIATOR

    def test_turn_order_has_exactly_three_personas(self):
        from app.services.debate_service import DebateService

        assert len(DebateService.TURN_ORDER) == 3

    def test_turn_order_wraps_round_robin(self):
        from app.services.debate_service import DebateService

        order = DebateService.TURN_ORDER
        assert order[3 % len(order)] == AgentPersona.LEGACY_KEEPER
        assert order[4 % len(order)] == AgentPersona.INNOVATOR
        assert order[5 % len(order)] == AgentPersona.MEDIATOR


# ══════════════════════════════════════════════════════════════════
# DebateSession.add_turn (model helper — no DB)
# ══════════════════════════════════════════════════════════════════


class TestDebateSessionAddTurn:
    def _make_session(self) -> DebateSession:
        return build_debate_session()

    def test_first_turn_has_turn_number_1(self):
        debate = self._make_session()
        debate.add_turn(persona="LEGACY_KEEPER", response="response 1")
        assert debate.debate_history[0]["turn_number"] == 1

    def test_second_turn_has_turn_number_2(self):
        debate = self._make_session()
        debate.add_turn(persona="LEGACY_KEEPER", response="r1")
        debate.add_turn(persona="INNOVATOR", response="r2")
        assert debate.debate_history[1]["turn_number"] == 2

    def test_total_turns_incremented(self):
        debate = self._make_session()
        assert debate.total_turns == 0
        debate.add_turn(persona="LEGACY_KEEPER", response="r")
        assert debate.total_turns == 1
        debate.add_turn(persona="INNOVATOR", response="r2")
        assert debate.total_turns == 2

    def test_persona_stored_correctly(self):
        debate = self._make_session()
        debate.add_turn(persona="INNOVATOR", response="innovation text")
        assert debate.debate_history[0]["persona"] == "INNOVATOR"

    def test_response_stored_correctly(self):
        debate = self._make_session()
        debate.add_turn(persona="MEDIATOR", response="consensus text")
        assert debate.debate_history[0]["response"] == "consensus text"

    def test_sentiment_stored(self):
        debate = self._make_session()
        debate.add_turn(persona="LEGACY_KEEPER", response="r", sentiment="contentious")
        assert debate.debate_history[0]["sentiment"] == "contentious"

    def test_key_points_stored(self):
        debate = self._make_session()
        debate.add_turn(
            persona="LEGACY_KEEPER",
            response="r",
            key_points=["backward compatibility", "stability"],
        )
        assert debate.debate_history[0]["key_points"] == [
            "backward compatibility",
            "stability",
        ]

    def test_key_points_default_empty_list(self):
        debate = self._make_session()
        debate.add_turn(persona="LEGACY_KEEPER", response="r")
        assert debate.debate_history[0]["key_points"] == []

    def test_bias_alignment_score_stored(self):
        debate = self._make_session()
        debate.add_turn(persona="INNOVATOR", response="r", bias_alignment_score=0.85)
        assert debate.debate_history[0]["bias_alignment_score"] == 0.85

    def test_timestamp_present_in_turn(self):
        debate = self._make_session()
        debate.add_turn(persona="MEDIATOR", response="r")
        assert "timestamp" in debate.debate_history[0]

    def test_initialises_history_when_none(self):
        debate = self._make_session()
        debate.debate_history = None
        debate.add_turn(persona="LEGACY_KEEPER", response="r")
        assert len(debate.debate_history) == 1

    def test_six_turns_stored(self):
        debate = self._make_session()
        personas = ["LEGACY_KEEPER", "INNOVATOR", "MEDIATOR"] * 2
        for i, p in enumerate(personas):
            debate.add_turn(persona=p, response=f"turn {i}")
        assert len(debate.debate_history) == 6
        assert debate.total_turns == 6


# ══════════════════════════════════════════════════════════════════
# DebateSession.complete() (model helper)
# ══════════════════════════════════════════════════════════════════


class TestDebateSessionComplete:
    def test_sets_consensus_reached(self):
        debate = build_debate_session()
        debate.complete(consensus_reached=True, consensus_type=ConsensusType.COMPROMISE)
        assert debate.consensus_reached is True

    def test_sets_consensus_type(self):
        debate = build_debate_session()
        debate.complete(consensus_reached=True, consensus_type=ConsensusType.UNANIMOUS)
        assert debate.consensus_type == ConsensusType.UNANIMOUS

    def test_sets_final_proposal(self):
        debate = build_debate_session()
        debate.complete(
            consensus_reached=True,
            consensus_type=ConsensusType.COMPROMISE,
            final_proposal="Use strangler-fig pattern.",
        )
        assert debate.final_consensus_proposal == "Use strangler-fig pattern."

    def test_sets_completed_at(self):
        debate = build_debate_session()
        debate.complete(consensus_reached=False, consensus_type=ConsensusType.TIMEOUT)
        assert debate.completed_at is not None

    def test_duration_calculated_when_started_at_set(self):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        debate = build_debate_session()
        debate.started_at = now - timedelta(seconds=30)
        debate.complete(consensus_reached=True, consensus_type=ConsensusType.MAJORITY)
        assert debate.duration_seconds is not None
        assert debate.duration_seconds >= 30

    def test_timeout_sets_false_consensus(self):
        debate = build_debate_session()
        debate.complete(consensus_reached=False, consensus_type=ConsensusType.TIMEOUT)
        assert debate.consensus_reached is False
        assert debate.consensus_type == ConsensusType.TIMEOUT


# ══════════════════════════════════════════════════════════════════
# DebateSession.calculate_persona_consistency
# ══════════════════════════════════════════════════════════════════


class TestCalculatePersonaConsistency:
    def test_averages_three_equal_scores(self):
        debate = build_debate_session()
        debate.legacy_keeper_consistency = 0.9
        debate.innovator_consistency = 0.9
        debate.mediator_consistency = 0.9
        debate.calculate_persona_consistency()
        assert abs(debate.overall_persona_consistency - 0.9) < 0.001

    def test_averages_mixed_scores(self):
        debate = build_debate_session()
        debate.legacy_keeper_consistency = 0.8
        debate.innovator_consistency = 0.6
        debate.mediator_consistency = 1.0
        debate.calculate_persona_consistency()
        assert abs(debate.overall_persona_consistency - 0.8) < 0.001

    def test_ignores_zero_scores(self):
        """Personas that didn't participate (score=0) are excluded from average."""
        debate = build_debate_session()
        debate.legacy_keeper_consistency = 0.9
        debate.innovator_consistency = 0.0
        debate.mediator_consistency = 0.0
        debate.calculate_persona_consistency()
        assert abs(debate.overall_persona_consistency - 0.9) < 0.001

    def test_all_zero_scores_gives_zero(self):
        debate = build_debate_session()
        debate.legacy_keeper_consistency = 0.0
        debate.innovator_consistency = 0.0
        debate.mediator_consistency = 0.0
        debate.calculate_persona_consistency()
        assert debate.overall_persona_consistency == 0.0


# ══════════════════════════════════════════════════════════════════
# DebateService._calculate_conflict_density
# ══════════════════════════════════════════════════════════════════


class TestCalculateConflictDensity:
    async def test_all_contentious_turns_gives_density_1(self):
        debate = build_debate_session()
        for i in range(3):
            debate.debate_history.append(
                {
                    "persona": "LEGACY_KEEPER",
                    "response": "however, I disagree with this risk",
                    "turn_number": i + 1,
                }
            )
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        svc = _make_service(session)
        density = await svc._calculate_conflict_density(debate.id)
        assert density == 1.0

    async def test_no_conflict_keywords_gives_density_0(self):
        debate = build_debate_session()
        debate.debate_history = [
            {
                "persona": "MEDIATOR",
                "response": "I fully agree with this approach.",
                "turn_number": 1,
            }
        ]
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        svc = _make_service(session)
        density = await svc._calculate_conflict_density(debate.id)
        assert density == 0.0

    async def test_half_contentious_gives_density_half(self):
        debate = build_debate_session()
        debate.debate_history = [
            {
                "persona": "LEGACY_KEEPER",
                "response": "however I disagree",
                "turn_number": 1,
            },
            {"persona": "INNOVATOR", "response": "I fully agree", "turn_number": 2},
        ]
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        svc = _make_service(session)
        density = await svc._calculate_conflict_density(debate.id)
        assert density == 0.5

    async def test_empty_debate_returns_zero(self):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = _make_service(session)
        density = await svc._calculate_conflict_density(uuid4())
        assert density == 0.0

    async def test_debate_with_empty_history_returns_zero(self):
        debate = build_debate_session()
        debate.debate_history = []
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        svc = _make_service(session)
        density = await svc._calculate_conflict_density(debate.id)
        assert density == 0.0

    async def test_all_conflict_keywords_detected(self):
        """Each keyword in the list should count as a conflict."""
        debate = build_debate_session()
        keywords = [
            "however",
            "disagree",
            "risk",
            "concern",
            "but",
            "challenge",
            "problematic",
            "issue",
        ]
        debate.debate_history = [
            {"persona": "LEGACY_KEEPER", "response": kw, "turn_number": i + 1}
            for i, kw in enumerate(keywords)
        ]
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        svc = _make_service(session)
        density = await svc._calculate_conflict_density(debate.id)
        assert density == 1.0


# ══════════════════════════════════════════════════════════════════
# DebateService._calculate_persona_consistency
# ══════════════════════════════════════════════════════════════════


class TestCalculatePersonaConsistencyService:
    async def test_writes_correct_scores_per_persona(self):
        debate = build_debate_session()
        debate.debate_history = [
            {
                "persona": "LEGACY_KEEPER",
                "response": "r",
                "turn_number": 1,
                "bias_alignment_score": 0.9,
            },
            {
                "persona": "INNOVATOR",
                "response": "r",
                "turn_number": 2,
                "bias_alignment_score": 0.7,
            },
            {
                "persona": "MEDIATOR",
                "response": "r",
                "turn_number": 3,
                "bias_alignment_score": 0.5,
            },
        ]
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        session.add = MagicMock()
        session.commit = AsyncMock()
        svc = _make_service(session)

        await svc._calculate_persona_consistency(debate.id)

        assert abs(debate.legacy_keeper_consistency - 0.9) < 0.001
        assert abs(debate.innovator_consistency - 0.7) < 0.001
        assert abs(debate.mediator_consistency - 0.5) < 0.001

    async def test_averages_multiple_turns_same_persona(self):
        debate = build_debate_session()
        debate.debate_history = [
            {
                "persona": "LEGACY_KEEPER",
                "response": "r",
                "turn_number": 1,
                "bias_alignment_score": 0.8,
            },
            {
                "persona": "LEGACY_KEEPER",
                "response": "r",
                "turn_number": 4,
                "bias_alignment_score": 0.6,
            },
        ]
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        session.add = MagicMock()
        session.commit = AsyncMock()
        svc = _make_service(session)

        await svc._calculate_persona_consistency(debate.id)

        assert abs(debate.legacy_keeper_consistency - 0.7) < 0.001

    async def test_missing_bias_score_defaults_to_0_5(self):
        debate = build_debate_session()
        debate.debate_history = [
            {
                "persona": "INNOVATOR",
                "response": "r",
                "turn_number": 1,
            },  # no bias_alignment_score
        ]
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        session.add = MagicMock()
        session.commit = AsyncMock()
        svc = _make_service(session)

        await svc._calculate_persona_consistency(debate.id)

        assert abs(debate.innovator_consistency - 0.5) < 0.001

    async def test_no_debate_returns_early(self):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = _make_service(session)
        # Should not raise
        await svc._calculate_persona_consistency(uuid4())
        session.commit.assert_not_awaited()

    async def test_commits_updated_scores(self):
        debate = build_debate_session()
        debate.debate_history = [
            {
                "persona": "MEDIATOR",
                "response": "r",
                "turn_number": 1,
                "bias_alignment_score": 0.8,
            },
        ]
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        session.add = MagicMock()
        session.commit = AsyncMock()
        svc = _make_service(session)

        await svc._calculate_persona_consistency(debate.id)

        session.add.assert_called_once_with(debate)
        session.commit.assert_awaited_once()


# ══════════════════════════════════════════════════════════════════
# DebateService._get_debate_history_from_session
# ══════════════════════════════════════════════════════════════════


class TestGetDebateHistoryFromSession:
    def test_returns_empty_list_when_history_none(self):
        svc = _make_service()
        debate = build_debate_session()
        debate.debate_history = None
        assert svc._get_debate_history_from_session(debate) == []

    def test_returns_debate_history_list(self):
        svc = _make_service()
        debate = build_complete_debate()
        history = svc._get_debate_history_from_session(debate)
        assert len(history) == 3

    def test_returns_empty_list_for_empty_history(self):
        svc = _make_service()
        debate = build_debate_session()
        assert svc._get_debate_history_from_session(debate) == []


# ══════════════════════════════════════════════════════════════════
# DebateService._get_debate_history (async DB read)
# ══════════════════════════════════════════════════════════════════


class TestGetDebateHistoryAsync:
    async def test_returns_history_for_existing_debate(self):
        debate = build_complete_debate()
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        svc = _make_service(session)

        history = await svc._get_debate_history(debate.id)
        assert len(history) == 3

    async def test_returns_empty_list_when_debate_missing(self):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = _make_service(session)

        history = await svc._get_debate_history(uuid4())
        assert history == []

    async def test_returns_empty_list_when_history_is_none(self):
        debate = build_debate_session()
        debate.debate_history = None
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        svc = _make_service(session)

        history = await svc._get_debate_history(debate.id)
        assert history == []


# ══════════════════════════════════════════════════════════════════
# DebateService._check_consensus
# ══════════════════════════════════════════════════════════════════


class TestCheckConsensus:
    def _debate_with_3_turns(self) -> DebateSession:
        debate = build_debate_session()
        for i, p in enumerate(["LEGACY_KEEPER", "INNOVATOR", "MEDIATOR"]):
            debate.debate_history.append(
                {
                    "turn_number": i + 1,
                    "persona": p,
                    "response": "A thoughtful response about the architecture.",
                }
            )
        return debate

    async def test_returns_false_when_debate_missing(self):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = _make_service(session)

        reached, confidence = await svc._check_consensus(uuid4(), threshold=0.8)
        assert reached is False
        assert confidence == 0.0

    async def test_returns_false_when_fewer_than_3_turns(self):
        debate = build_in_progress_debate(turns_done=1)
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        svc = _make_service(session)

        reached, confidence = await svc._check_consensus(debate.id, threshold=0.8)
        assert reached is False

    async def test_consensus_detected_above_threshold(self):
        debate = self._debate_with_3_turns()
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        svc = _make_service(session)

        with patch(
            "app.services.debate_service.ai_service.generate_structured",
            new=AsyncMock(
                return_value={
                    "consensus_reached": True,
                    "confidence": 0.92,
                    "reasoning": "All personas agreed on strangler-fig.",
                }
            ),
        ):
            reached, confidence = await svc._check_consensus(debate.id, threshold=0.8)

        assert reached is True
        assert confidence == 0.92

    async def test_no_consensus_below_threshold(self):
        debate = self._debate_with_3_turns()
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        svc = _make_service(session)

        with patch(
            "app.services.debate_service.ai_service.generate_structured",
            new=AsyncMock(
                return_value={
                    "consensus_reached": True,
                    "confidence": 0.60,  # below threshold=0.8
                    "reasoning": "Weak alignment.",
                }
            ),
        ):
            reached, confidence = await svc._check_consensus(debate.id, threshold=0.8)

        assert reached is False
        assert confidence == 0.60

    async def test_ai_failure_returns_false_zero(self):
        debate = self._debate_with_3_turns()
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        svc = _make_service(session)

        with patch(
            "app.services.debate_service.ai_service.generate_structured",
            new=AsyncMock(side_effect=RuntimeError("AI unavailable")),
        ):
            reached, confidence = await svc._check_consensus(debate.id, threshold=0.8)

        assert reached is False
        assert confidence == 0.0


# ══════════════════════════════════════════════════════════════════
# DebateService._get_rag_context
# ══════════════════════════════════════════════════════════════════


class TestGetRagContext:
    async def test_returns_fallback_when_no_project_documents(self):
        proposal = _make_proposal(project_id=10)
        session = _make_db_session(exec_returns=[[]])  # no doc IDs
        svc = _make_service(session)

        context = await svc._get_rag_context(proposal)
        assert "No project documents" in context

    async def test_returns_fallback_when_no_chunks_found(self):
        proposal = _make_proposal(project_id=10)
        # exec returns [doc_id], then vector_service returns []
        session = _make_db_session(exec_returns=[[1, 2]])
        svc = _make_service(session)
        svc.vector_service.search_similar = AsyncMock(return_value=[])

        context = await svc._get_rag_context(proposal)
        assert "No relevant" in context

    async def test_returns_formatted_chunks_when_found(self):
        proposal = _make_proposal(project_id=10)
        session = _make_db_session(exec_returns=[[1]])
        svc = _make_service(session)

        chunk = MagicMock()
        chunk.document_id = 1
        chunk.chunk_index = 0
        chunk.content = "Legacy monolith architecture overview."
        svc.vector_service.search_similar = AsyncMock(return_value=[chunk])

        context = await svc._get_rag_context(proposal)
        assert "Legacy monolith" in context
        assert "Document 1" in context

    async def test_returns_fallback_on_exception(self):
        proposal = _make_proposal(project_id=10)
        session = AsyncMock()
        session.exec = AsyncMock(side_effect=RuntimeError("DB error"))
        svc = _make_service(session)

        context = await svc._get_rag_context(proposal)
        assert "retrieval failed" in context.lower() or "failed" in context.lower()


# ══════════════════════════════════════════════════════════════════
# DebateService._execute_turn
# ══════════════════════════════════════════════════════════════════


class TestExecuteTurn:
    def _make_svc_with_persona_mock(
        self, response_text="Legacy systems must be preserved."
    ):
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        svc = _make_service(session)
        svc.persona_service.generate_response = AsyncMock(
            return_value={
                "response_text": response_text,
                "quality_attributes_mentioned": ["reliability", "stability"],
                "bias_alignment_score": 0.88,
            }
        )
        return svc

    async def test_appends_turn_to_debate_history(self):
        debate = build_debate_session()
        proposal = _make_proposal()
        svc = self._make_svc_with_persona_mock()

        await svc._execute_turn(
            debate=debate,
            proposal=proposal,
            persona=AgentPersona.LEGACY_KEEPER,
            turn_index=0,
            rag_context="Some context.",
        )

        assert debate.total_turns == 1

    async def test_turn_dict_returned_with_bias_score(self):
        debate = build_debate_session()
        proposal = _make_proposal()
        svc = self._make_svc_with_persona_mock()

        turn = await svc._execute_turn(
            debate=debate,
            proposal=proposal,
            persona=AgentPersona.LEGACY_KEEPER,
            turn_index=0,
            rag_context="context",
        )

        assert turn["bias_alignment_score"] == 0.88

    async def test_contentious_sentiment_detected(self):
        debate = build_debate_session()
        proposal = _make_proposal()
        svc = self._make_svc_with_persona_mock(
            response_text="However, I disagree with this approach."
        )

        await svc._execute_turn(
            debate=debate,
            proposal=proposal,
            persona=AgentPersona.LEGACY_KEEPER,
            turn_index=0,
            rag_context="context",
        )

        assert debate.debate_history[0]["sentiment"] == "contentious"

    async def test_agreeable_sentiment_detected(self):
        debate = build_debate_session()
        proposal = _make_proposal()
        svc = self._make_svc_with_persona_mock(
            response_text="I fully support this architectural direction."
        )

        await svc._execute_turn(
            debate=debate,
            proposal=proposal,
            persona=AgentPersona.INNOVATOR,
            turn_index=0,
            rag_context="context",
        )

        assert debate.debate_history[0]["sentiment"] == "agreeable"

    async def test_calls_persona_service_with_correct_slug(self):
        debate = build_debate_session()
        proposal = _make_proposal()
        svc = self._make_svc_with_persona_mock()

        await svc._execute_turn(
            debate=debate,
            proposal=proposal,
            persona=AgentPersona.INNOVATOR,
            turn_index=1,
            rag_context="context",
        )

        call_kwargs = svc.persona_service.generate_response.call_args
        assert call_kwargs.kwargs["persona_slug"] == "innovator"

    async def test_raises_debate_exception_on_persona_failure(self):
        debate = build_debate_session()
        proposal = _make_proposal()
        session = AsyncMock()
        session.add = MagicMock()
        svc = _make_service(session)
        svc.persona_service.generate_response = AsyncMock(
            side_effect=RuntimeError("AI timeout")
        )

        with pytest.raises(DebateException, match="Failed to generate"):
            await svc._execute_turn(
                debate=debate,
                proposal=proposal,
                persona=AgentPersona.MEDIATOR,
                turn_index=2,
                rag_context="context",
            )

    async def test_commits_after_turn(self):
        debate = build_debate_session()
        proposal = _make_proposal()
        svc = self._make_svc_with_persona_mock()

        await svc._execute_turn(
            debate=debate,
            proposal=proposal,
            persona=AgentPersona.LEGACY_KEEPER,
            turn_index=0,
            rag_context="context",
        )

        svc.session.commit.assert_awaited()


# ══════════════════════════════════════════════════════════════════
# DebateService._generate_final_proposal
# ══════════════════════════════════════════════════════════════════


class TestGenerateFinalProposal:
    async def test_returns_generated_text(self):
        debate = build_complete_debate()
        proposal = _make_proposal()
        # exec returns no template (first() = None), so fallback system prompt used
        session = _make_db_session(exec_returns=[None])
        svc = _make_service(session)

        with patch(
            "app.services.debate_service.ai_service.generate_text",
            new=AsyncMock(return_value="Final consensus: adopt strangler-fig."),
        ):
            result = await svc._generate_final_proposal(debate, proposal)

        assert "strangler-fig" in result

    async def test_falls_back_on_ai_failure(self):
        debate = build_complete_debate()
        proposal = _make_proposal()
        session = _make_db_session(exec_returns=[None])
        svc = _make_service(session)

        with patch(
            "app.services.debate_service.ai_service.generate_text",
            new=AsyncMock(side_effect=RuntimeError("API error")),
        ):
            result = await svc._generate_final_proposal(debate, proposal)

        assert "Failed" in result

    async def test_uses_template_when_available(self):
        debate = build_complete_debate()
        proposal = _make_proposal()
        template = MagicMock()
        template.system_prompt = "Custom synthesis system prompt."
        session = _make_db_session(exec_returns=[template])
        svc = _make_service(session)

        captured_system = {}

        async def _capture_generate(system_prompt, **kwargs):
            captured_system["value"] = system_prompt
            return "Final proposal text."

        with patch(
            "app.services.debate_service.ai_service.generate_text",
            new=AsyncMock(side_effect=_capture_generate),
        ):
            await svc._generate_final_proposal(debate, proposal)

        assert captured_system["value"] == "Custom synthesis system prompt."


# ══════════════════════════════════════════════════════════════════
# DebateService.get_debate_by_id
# ══════════════════════════════════════════════════════════════════


class TestGetDebateById:
    async def test_raises_not_found_when_none(self):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = _make_service(session)
        with pytest.raises(NotFoundException):
            await svc.get_debate_by_id(uuid4(), user_id=1, user_role=UserRole.USER)

    async def test_returns_debate_when_found(self):
        debate = build_complete_debate()
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        svc = _make_service(session)
        svc._get_proposal_with_access = AsyncMock(return_value=MagicMock())

        result = await svc.get_debate_by_id(
            debate.id, user_id=1, user_role=UserRole.USER
        )
        assert result == debate

    async def test_checks_proposal_access(self):
        debate = build_complete_debate()
        session = AsyncMock()
        session.get = AsyncMock(return_value=debate)
        svc = _make_service(session)
        svc._get_proposal_with_access = AsyncMock(return_value=MagicMock())

        await svc.get_debate_by_id(debate.id, user_id=42, user_role=UserRole.USER)

        svc._get_proposal_with_access.assert_awaited_once_with(
            debate.proposal_id, 42, UserRole.USER
        )


# ══════════════════════════════════════════════════════════════════
# DebateService.get_debates_by_proposal
# ══════════════════════════════════════════════════════════════════


class TestGetDebatesByProposal:
    async def test_returns_empty_list_when_no_debates(self):
        session = _make_db_session(exec_returns=[[]])
        svc = _make_service(session)
        svc._get_proposal_with_access = AsyncMock(return_value=MagicMock())

        result = await svc.get_debates_by_proposal(
            1, user_id=1, user_role=UserRole.USER
        )
        assert result == []

    async def test_returns_list_of_debates(self):
        d1 = build_complete_debate(proposal_id=1)
        d2 = build_complete_debate(proposal_id=1)
        session = _make_db_session(exec_returns=[[d1, d2]])
        svc = _make_service(session)
        svc._get_proposal_with_access = AsyncMock(return_value=MagicMock())

        result = await svc.get_debates_by_proposal(
            1, user_id=1, user_role=UserRole.USER
        )
        assert len(result) == 2

    async def test_raises_not_found_when_access_denied(self):
        session = _make_db_session()
        svc = _make_service(session)
        svc._get_proposal_with_access = AsyncMock(
            side_effect=NotFoundException("Proposal 99 not found")
        )

        with pytest.raises(NotFoundException):
            await svc.get_debates_by_proposal(99, user_id=1, user_role=UserRole.USER)

    async def test_access_check_called_before_db_query(self):
        """Access must be verified even if the query would return nothing."""
        session = _make_db_session(exec_returns=[[]])
        svc = _make_service(session)
        access_mock = AsyncMock(return_value=MagicMock())
        svc._get_proposal_with_access = access_mock

        await svc.get_debates_by_proposal(5, user_id=7, user_role=UserRole.USER)

        access_mock.assert_awaited_once_with(5, 7, UserRole.USER)


# ══════════════════════════════════════════════════════════════════
# DebateService.get_debate_turns — sorted by turn_number
# ══════════════════════════════════════════════════════════════════


class TestGetDebateTurns:
    async def test_turns_sorted_ascending_by_turn_number(self):
        debate = build_debate_session()
        debate.debate_history = [
            {"turn_number": 3, "persona": "MEDIATOR", "response": "r3"},
            {"turn_number": 1, "persona": "LEGACY_KEEPER", "response": "r1"},
            {"turn_number": 2, "persona": "INNOVATOR", "response": "r2"},
        ]
        session = AsyncMock()
        svc = _make_service(session)
        svc.get_debate_by_id = AsyncMock(return_value=debate)

        turns = await svc.get_debate_turns(
            debate.id, user_id=1, user_role=UserRole.USER
        )
        assert [t["turn_number"] for t in turns] == [1, 2, 3]

    async def test_empty_history_returns_empty_list(self):
        debate = build_debate_session()
        debate.debate_history = []
        session = AsyncMock()
        svc = _make_service(session)
        svc.get_debate_by_id = AsyncMock(return_value=debate)

        turns = await svc.get_debate_turns(
            debate.id, user_id=1, user_role=UserRole.USER
        )
        assert turns == []

    async def test_none_history_returns_empty_list(self):
        debate = build_debate_session()
        debate.debate_history = None
        session = AsyncMock()
        svc = _make_service(session)
        svc.get_debate_by_id = AsyncMock(return_value=debate)

        turns = await svc.get_debate_turns(
            debate.id, user_id=1, user_role=UserRole.USER
        )
        assert turns == []


# ══════════════════════════════════════════════════════════════════
# DebateService.conduct_debate — full orchestration
# ══════════════════════════════════════════════════════════════════


class TestConductDebate:
    """
    Tests for the main orchestration method.

    External dependencies are mocked at the service level:
      - _get_proposal_with_access  → returns a stub Proposal
      - _get_rag_context           → returns "mock context"
      - _execute_turn              → records calls, returns turn dict
      - _check_consensus           → controlled via parametrise
      - _generate_final_proposal   → returns "final text"
      - _calculate_conflict_density → returns 0.4
      - _calculate_persona_consistency → no-op async
    """

    def _make_full_svc(
        self,
        consensus_after_turn: int | None = 3,
        consensus_confidence: float = 0.9,
        max_turns: int = 6,
    ):
        """
        Build a DebateService with all external calls patched.

        consensus_after_turn: which turn (1-indexed) triggers consensus,
                              or None for no consensus (timeout).
        """
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.rollback = AsyncMock()

        proposal = _make_proposal()

        # session.get is called inside commit/refresh cycles; we return the
        # same debate object for all .get() calls so later reads stay consistent.
        debate_holder = {}

        async def _fake_refresh(obj):
            if isinstance(obj, DebateSession):
                debate_holder["debate"] = obj

        session.refresh = AsyncMock(side_effect=_fake_refresh)

        svc = _make_service(session)

        svc._get_proposal_with_access = AsyncMock(return_value=proposal)
        svc._get_rag_context = AsyncMock(return_value="RAG context text.")

        turn_call_count = {"n": 0}

        async def _fake_execute_turn(
            debate, proposal, persona, turn_index, rag_context
        ):
            turn_call_count["n"] += 1
            debate.add_turn(
                persona=persona.value,
                response="A thoughtful response.",
                sentiment="agreeable",
                bias_alignment_score=0.8,
            )
            return debate.debate_history[-1]

        svc._execute_turn = AsyncMock(side_effect=_fake_execute_turn)
        svc._turn_call_count = turn_call_count

        # Consensus fires after the Mediator turn (every 3rd turn = index 2, 5, …)
        async def _fake_check_consensus(debate_id, threshold):
            n = turn_call_count["n"]
            if consensus_after_turn and n >= consensus_after_turn:
                return True, consensus_confidence
            return False, 0.3

        svc._check_consensus = AsyncMock(side_effect=_fake_check_consensus)
        svc._generate_final_proposal = AsyncMock(return_value="Final proposal text.")
        svc._calculate_conflict_density = AsyncMock(return_value=0.4)
        svc._calculate_persona_consistency = AsyncMock()

        return svc

    async def test_returns_debate_session(self):
        svc = self._make_full_svc()
        debate = await svc.conduct_debate(
            proposal_id=1, user_id=1, user_role=UserRole.USER
        )
        assert isinstance(debate, DebateSession)

    async def test_debate_is_completed_on_consensus(self):
        svc = self._make_full_svc(consensus_after_turn=3)
        debate = await svc.conduct_debate(
            proposal_id=1, user_id=1, user_role=UserRole.USER
        )
        assert debate.consensus_reached is True
        assert debate.consensus_type == ConsensusType.UNANIMOUS

    async def test_debate_times_out_without_consensus(self):
        svc = self._make_full_svc(consensus_after_turn=None, max_turns=6)
        debate = await svc.conduct_debate(
            proposal_id=1, user_id=1, user_role=UserRole.USER, max_turns=6
        )
        assert debate.consensus_reached is False
        assert debate.consensus_type == ConsensusType.TIMEOUT

    async def test_max_turns_respected(self):
        svc = self._make_full_svc(consensus_after_turn=None, max_turns=4)
        await svc.conduct_debate(
            proposal_id=1, user_id=1, user_role=UserRole.USER, max_turns=4
        )
        assert svc._turn_call_count["n"] == 4

    async def test_proposal_not_found_raises(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        svc = _make_service(session)
        svc._get_proposal_with_access = AsyncMock(
            side_effect=NotFoundException("Proposal 99 not found")
        )

        with pytest.raises(NotFoundException):
            await svc.conduct_debate(proposal_id=99, user_id=1, user_role=UserRole.USER)

    async def test_persona_failure_raises_debate_exception(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.rollback = AsyncMock()
        svc = _make_service(session)
        svc._get_proposal_with_access = AsyncMock(return_value=_make_proposal())
        svc._get_rag_context = AsyncMock(return_value="context")
        svc._execute_turn = AsyncMock(
            side_effect=DebateException("Failed to generate LEGACY_KEEPER response")
        )
        svc._calculate_conflict_density = AsyncMock(return_value=0.0)
        svc._calculate_persona_consistency = AsyncMock()
        svc._check_consensus = AsyncMock(return_value=(False, 0.0))

        with pytest.raises(DebateException):
            await svc.conduct_debate(proposal_id=1, user_id=1, user_role=UserRole.USER)

    async def test_conflict_density_calculated_on_completion(self):
        svc = self._make_full_svc(consensus_after_turn=3)
        await svc.conduct_debate(proposal_id=1, user_id=1, user_role=UserRole.USER)
        svc._calculate_conflict_density.assert_awaited()

    async def test_persona_consistency_calculated_on_completion(self):
        svc = self._make_full_svc(consensus_after_turn=3)
        await svc.conduct_debate(proposal_id=1, user_id=1, user_role=UserRole.USER)
        svc._calculate_persona_consistency.assert_awaited()

    async def test_final_proposal_generated_on_consensus(self):
        svc = self._make_full_svc(consensus_after_turn=3)
        await svc.conduct_debate(proposal_id=1, user_id=1, user_role=UserRole.USER)
        svc._generate_final_proposal.assert_awaited()

    async def test_final_proposal_not_generated_on_timeout(self):
        svc = self._make_full_svc(consensus_after_turn=None)
        await svc.conduct_debate(proposal_id=1, user_id=1, user_role=UserRole.USER)
        svc._generate_final_proposal.assert_not_awaited()

    async def test_duration_seconds_set(self):
        svc = self._make_full_svc(consensus_after_turn=3)
        debate = await svc.conduct_debate(
            proposal_id=1, user_id=1, user_role=UserRole.USER
        )
        assert debate.duration_seconds is not None
        assert debate.duration_seconds >= 0

    async def test_completed_at_set(self):
        svc = self._make_full_svc(consensus_after_turn=3)
        debate = await svc.conduct_debate(
            proposal_id=1, user_id=1, user_role=UserRole.USER
        )
        assert debate.completed_at is not None

    async def test_cleanup_attempted_on_error(self):
        """On failure, the service should rollback and attempt to save a TIMEOUT record."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.rollback = AsyncMock()
        svc = _make_service(session)
        svc._get_proposal_with_access = AsyncMock(return_value=_make_proposal())
        svc._get_rag_context = AsyncMock(return_value="context")
        svc._execute_turn = AsyncMock(side_effect=RuntimeError("unexpected crash"))
        svc._calculate_conflict_density = AsyncMock(return_value=0.0)
        svc._calculate_persona_consistency = AsyncMock()
        svc._check_consensus = AsyncMock(return_value=(False, 0.0))

        with pytest.raises(DebateException):
            await svc.conduct_debate(proposal_id=1, user_id=1, user_role=UserRole.USER)

        session.rollback.assert_awaited()
