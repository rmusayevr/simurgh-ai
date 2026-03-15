"""
Debate factory fixtures.

Covers DebateSession and DebateTurn instances for debate service and API tests.
Includes helpers for building partial (in-progress) and complete debate sessions.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from uuid import uuid4, UUID

from app.models.debate import DebateSession, ConsensusType
from app.models.proposal import AgentPersona


# ── Turn order constant (matches debate_service logic) ────────────────────────

PERSONA_ORDER = [
    AgentPersona.LEGACY_KEEPER.value,
    AgentPersona.INNOVATOR.value,
    AgentPersona.MEDIATOR.value,
]


# ── Low-level factories ────────────────────────────────────────────────────────


def build_debate_turn(
    turn_number: int = 1,
    persona: str = AgentPersona.LEGACY_KEEPER.value,
    response: str = "From the Legacy Keeper: we must ensure backward compatibility.",
    sentiment: str | None = "contentious",
    key_points: list[str] | None = None,
) -> dict:
    """
    Build a debate turn dict (stored as JSONB in DebateSession.debate_history).

    Returns a plain dict (not a DebateTurn model) because that is how the
    debate_history JSONB column stores the turns.
    """
    return {
        "turn_number": turn_number,
        "persona": persona,
        "response": response,
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "sentiment": sentiment,
        "key_points": key_points or ["backward compatibility", "risk mitigation"],
    }


def build_debate_session(
    id: UUID | None = None,
    proposal_id: int = 1,
    debate_history: list[dict] | None = None,
    final_consensus_proposal: str | None = None,
    consensus_reached: bool = False,
    consensus_type: ConsensusType | None = None,
    total_turns: int = 0,
    duration_seconds: float | None = None,
    conflict_density: float = 0.0,
    legacy_keeper_consistency: float | None = None,
    innovator_consistency: float | None = None,
    mediator_consistency: float | None = None,
) -> DebateSession:
    """
    Build an in-memory DebateSession.

    Args:
        id:                         UUID (auto-generated if not provided)
        proposal_id:                FK to Proposal
        debate_history:             List of turn dicts (JSONB content)
        final_consensus_proposal:   Synthesized final recommendation
        consensus_reached:          Whether consensus was achieved
        consensus_type:             ConsensusType enum value
        total_turns:                Number of turns taken
        duration_seconds:           Debate duration
        conflict_density:           Ratio of contentious turns (0.0-1.0)
        legacy_keeper_consistency:  RQ2 persona consistency score
        innovator_consistency:      RQ2 persona consistency score
        mediator_consistency:       RQ2 persona consistency score
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return DebateSession(
        id=id or uuid4(),
        proposal_id=proposal_id,
        debate_history=debate_history or [],
        final_consensus_proposal=final_consensus_proposal,
        consensus_reached=consensus_reached,
        consensus_type=consensus_type,
        total_turns=total_turns,
        duration_seconds=duration_seconds,
        conflict_density=conflict_density,
        legacy_keeper_consistency=legacy_keeper_consistency,
        innovator_consistency=innovator_consistency,
        mediator_consistency=mediator_consistency,
        started_at=now,
        completed_at=now if consensus_reached else None,
    )


def build_complete_debate(proposal_id: int = 1) -> DebateSession:
    """
    Build a complete 3-turn debate session that reached COMPROMISE consensus.

    Turn order: Legacy Keeper → Innovator → Mediator
    """
    turns = [
        build_debate_turn(
            turn_number=1,
            persona=AgentPersona.LEGACY_KEEPER.value,
            response="We must preserve the existing integration contracts.",
            sentiment="contentious",
            key_points=["backward compatibility", "risk mitigation"],
        ),
        build_debate_turn(
            turn_number=2,
            persona=AgentPersona.INNOVATOR.value,
            response="A full rewrite would deliver 10× performance improvements.",
            sentiment="contentious",
            key_points=["performance", "scalability", "developer velocity"],
        ),
        build_debate_turn(
            turn_number=3,
            persona=AgentPersona.MEDIATOR.value,
            response=(
                "I propose a strangler-fig migration: "
                "we preserve contracts while incrementally modernising. "
                "Both sides agree this minimises risk while enabling progress."
            ),
            sentiment="agreeable",
            key_points=["incremental migration", "strangler-fig", "consensus"],
        ),
    ]

    return build_debate_session(
        proposal_id=proposal_id,
        debate_history=turns,
        final_consensus_proposal=(
            "Adopt a strangler-fig migration pattern, replacing monolith "
            "services one by one while maintaining API contracts."
        ),
        consensus_reached=True,
        consensus_type=ConsensusType.COMPROMISE,
        total_turns=3,
        duration_seconds=42.7,
        conflict_density=0.67,
        legacy_keeper_consistency=0.88,
        innovator_consistency=0.91,
        mediator_consistency=0.85,
    )


def build_in_progress_debate(
    proposal_id: int = 1, turns_done: int = 1
) -> DebateSession:
    """
    Build a debate session that is in progress (not yet complete).

    Args:
        proposal_id: FK to Proposal
        turns_done:  How many turns have already happened (1 or 2)
    """
    personas = PERSONA_ORDER[:turns_done]
    turns = [
        build_debate_turn(
            turn_number=i + 1,
            persona=personas[i],
            response=f"Turn {i + 1} response from {personas[i]}.",
        )
        for i in range(turns_done)
    ]

    return build_debate_session(
        proposal_id=proposal_id,
        debate_history=turns,
        consensus_reached=False,
        total_turns=turns_done,
    )


def build_timed_out_debate(proposal_id: int = 1) -> DebateSession:
    """Debate that reached the turn limit without consensus."""
    turns = []
    for round_num in range(6):  # max 6 rounds = 18 turns (3 personas × 6)
        persona = PERSONA_ORDER[round_num % 3]
        turns.append(
            build_debate_turn(
                turn_number=round_num + 1,
                persona=persona,
                response=f"Round {round_num + 1} — no agreement reached.",
                sentiment="contentious",
            )
        )

    return build_debate_session(
        proposal_id=proposal_id,
        debate_history=turns,
        consensus_reached=True,  # marked complete even on timeout
        consensus_type=ConsensusType.TIMEOUT,
        total_turns=6,
        duration_seconds=180.0,
        conflict_density=1.0,
    )


# ── pytest fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def test_debate_session() -> DebateSession:
    """Empty debate session (just started, no turns yet)."""
    return build_debate_session()


@pytest.fixture
def test_complete_debate() -> DebateSession:
    """Completed debate with COMPROMISE consensus."""
    return build_complete_debate()


@pytest.fixture
def test_in_progress_debate() -> DebateSession:
    """Debate after the first turn (Legacy Keeper spoke)."""
    return build_in_progress_debate(turns_done=1)


@pytest.fixture
def test_timed_out_debate() -> DebateSession:
    """Debate that ran to the 6-round limit without consensus."""
    return build_timed_out_debate()


@pytest.fixture
def make_debate_session():
    """
    Parameterizable debate session factory.

    Usage:
        def test_custom(make_debate_session):
            session = make_debate_session(proposal_id=5, total_turns=2)
    """
    return build_debate_session


@pytest.fixture
def make_debate_turn():
    """
    Parameterizable debate turn factory.

    Usage:
        def test_turn(make_debate_turn):
            turn = make_debate_turn(turn_number=2, persona="INNOVATOR")
    """
    return build_debate_turn
