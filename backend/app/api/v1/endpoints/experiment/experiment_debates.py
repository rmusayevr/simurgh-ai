"""
Experiment Debates - Debate session endpoints.

GET /experiment-data/debates
"""

import structlog
from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session
from app.models.debate import DebateSession

from app.api.v1.endpoints.experiment.experiment_helpers import _safe_mean

logger = structlog.get_logger()
router = APIRouter()


@router.get("/debates", summary="All debate sessions with turn-level detail")
async def list_debate_sessions(
    session: AsyncSession = Depends(get_session),
    consensus_only: bool = Query(default=False),
    include_turns: bool = Query(
        default=False,
        description="Include full debate_history (can be large)",
    ),
):
    """
    Returns all DebateSessions with metrics. Set include_turns=true to
    also return the complete turn-by-turn transcript.
    """
    stmt = select(DebateSession)
    if consensus_only:
        stmt = stmt.where(DebateSession.consensus_reached)
    stmt = stmt.order_by(DebateSession.started_at)

    debates = (await session.exec(stmt)).all()

    def _serialize(d: DebateSession) -> dict:
        out = {
            "debate_id": str(d.id),
            "proposal_id": d.proposal_id,
            "metrics": {
                "total_turns": d.total_turns,
                "duration_seconds": d.duration_seconds,
                "duration_minutes": round(d.duration_minutes, 2),
                "avg_seconds_per_turn": round(d.average_turn_duration, 2),
                "conflict_density": d.conflict_density,
                "is_high_conflict": d.is_high_conflict,
            },
            "consensus": {
                "reached": d.consensus_reached,
                "type": d.consensus_type.value if d.consensus_type else None,
                "confidence": d.consensus_confidence,
            },
            "persona_consistency": {
                "legacy_keeper": d.legacy_keeper_consistency,
                "innovator": d.innovator_consistency,
                "mediator": d.mediator_consistency,
                "overall": d.overall_persona_consistency,
            },
            "timestamps": {
                "started_at": d.started_at.isoformat(),
                "completed_at": d.completed_at.isoformat() if d.completed_at else None,
                "is_completed": d.is_completed,
            },
        }
        if include_turns:
            out["debate_history"] = d.debate_history or []
            out["final_consensus_proposal"] = d.final_consensus_proposal
        return out

    serialized = [_serialize(d) for d in debates]

    durations = [d.duration_seconds for d in debates if d.duration_seconds]
    turns = [d.total_turns for d in debates]

    return {
        "total": len(debates),
        "consensus_reached": sum(1 for d in debates if d.consensus_reached),
        "consensus_rate_pct": round(
            (
                sum(1 for d in debates if d.consensus_reached) / len(debates) * 100
                if debates
                else 0
            ),
            1,
        ),
        "aggregates": {
            "mean_duration_seconds": _safe_mean(durations),
            "mean_turns": _safe_mean(turns),
            "high_conflict_count": sum(1 for d in debates if d.is_high_conflict),
        },
        "debates": serialized,
    }
