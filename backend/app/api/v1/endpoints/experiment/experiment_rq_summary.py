"""
Experiment RQ Summary - Research question statistics endpoints.

GET /experiment-data/rq-summary
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session
from app.models.questionnaire import QuestionnaireResponse, ExperimentCondition
from app.models.debate import DebateSession
from app.models.persona_coding import PersonaCoding
from app.models.proposal import ProposalVariation, AgentPersona

from app.api.v1.endpoints.experiment.experiment_helpers import (
    _safe_mean,
    _safe_stdev,
    _cohen_d,
)

logger = structlog.get_logger()
router = APIRouter()


@router.get("/rq-summary", summary="Full RQ1 / RQ2 / RQ3 aggregate statistics")
async def get_rq_summary(
    session: AsyncSession = Depends(get_session),
):
    """
    Returns a single object with all thesis research-question metrics:
    - RQ1: Trust and quality Likert comparisons per condition
    - RQ2: Persona consistency from coded debate sessions
    - RQ3: Consensus efficiency (turn count and duration)
    Invalided questionnaires are excluded.
    """
    q_rows = (
        await session.exec(
            select(QuestionnaireResponse).where(QuestionnaireResponse.is_valid)
        )
    ).all()

    baseline_q = [r for r in q_rows if r.condition == ExperimentCondition.BASELINE]
    multi_q = [r for r in q_rows if r.condition == ExperimentCondition.MULTIAGENT]

    def _per_item(rows):
        if not rows:
            return {}
        fields = [
            "trust_overall",
            "risk_awareness",
            "technical_soundness",
            "balance",
            "actionability",
            "completeness",
        ]
        return {
            f: {
                "mean": _safe_mean([getattr(r, f) for r in rows]),
                "stdev": _safe_stdev([float(getattr(r, f)) for r in rows]),
            }
            for f in fields
        }

    codings = (await session.exec(select(PersonaCoding))).all()
    by_persona: dict[str, list[float]] = {}
    for c in codings:
        by_persona.setdefault(c.persona, []).append(c.consistency_score)

    debates = (await session.exec(select(DebateSession))).all()
    completed_debates = [d for d in debates if d.is_completed]

    baseline_vars = (
        await session.exec(
            select(ProposalVariation).where(
                ProposalVariation.agent_persona == AgentPersona.BASELINE
            )
        )
    ).all()
    baseline_gen_times = [
        v.generation_seconds for v in baseline_vars if v.generation_seconds is not None
    ]
    multi_durations = [
        d.duration_seconds for d in completed_debates if d.duration_seconds
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rq1_trust_and_quality": {
            "hypothesis": "Multi-agent proposals achieve higher trust scores than baseline",
            "n_baseline": len(baseline_q),
            "n_multiagent": len(multi_q),
            "composite_mean_score": {
                "baseline": _safe_mean([r.mean_score for r in baseline_q]),
                "multiagent": _safe_mean([r.mean_score for r in multi_q]),
                "baseline_stdev": _safe_stdev([r.mean_score for r in baseline_q]),
                "multiagent_stdev": _safe_stdev([r.mean_score for r in multi_q]),
                "cohen_d": _cohen_d(
                    [r.mean_score for r in multi_q],
                    [r.mean_score for r in baseline_q],
                ),
                "interpretation": (
                    "Cohen's d > 0 → multi-agent scores higher. "
                    "0.2=small, 0.5=medium, 0.8=large effect."
                ),
            },
            "per_item_baseline": _per_item(baseline_q),
            "per_item_multiagent": _per_item(multi_q),
        },
        "rq2_persona_consistency": {
            "hypothesis": "AI personas maintain consistent character throughout debates",
            "total_turns_coded": len(codings),
            "per_persona": {
                persona: {
                    "turns_coded": len(scores),
                    "mean_consistency": _safe_mean(scores),
                    "stdev": _safe_stdev(scores),
                    "pct_fully_consistent": round(
                        (
                            sum(1 for s in scores if s == 1.0) / len(scores) * 100
                            if scores
                            else 0
                        ),
                        1,
                    ),
                }
                for persona, scores in by_persona.items()
            },
            "hallucination_summary": {
                "total_coded": len(codings),
                "none": sum(1 for c in codings if c.hallucination.value == "no"),
                "minor": sum(1 for c in codings if c.hallucination.value == "minor"),
                "major": sum(1 for c in codings if c.hallucination.value == "major"),
            },
        },
        "rq3_consensus_efficiency": {
            "hypothesis": "Multi-agent approach reaches consensus efficiently",
            "baseline_generation": {
                "n": len(baseline_gen_times),
                "mean_seconds": _safe_mean(baseline_gen_times),
                "stdev_seconds": _safe_stdev(baseline_gen_times),
            },
            "multiagent_debates": {
                "n": len(completed_debates),
                "consensus_reached": sum(
                    1 for d in completed_debates if d.consensus_reached
                ),
                "consensus_rate_pct": round(
                    (
                        sum(1 for d in completed_debates if d.consensus_reached)
                        / len(completed_debates)
                        * 100
                        if completed_debates
                        else 0
                    ),
                    1,
                ),
                "mean_turns": _safe_mean(
                    [float(d.total_turns) for d in completed_debates]
                ),
                "mean_duration_seconds": _safe_mean(multi_durations),
                "stdev_duration_seconds": _safe_stdev(multi_durations),
                "mean_conflict_density": _safe_mean(
                    [d.conflict_density for d in completed_debates]
                ),
            },
            "efficiency_comparison_note": (
                "Compare baseline_generation.mean_seconds to "
                "multiagent_debates.mean_duration_seconds for RQ3."
            ),
        },
    }
