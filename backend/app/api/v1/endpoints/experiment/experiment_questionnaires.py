"""
Experiment Questionnaires - Questionnaire response endpoints.

GET /experiment-data/questionnaires
"""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session
from app.models.questionnaire import QuestionnaireResponse, ExperimentCondition

from app.api.v1.endpoints.experiment.experiment_helpers import _safe_mean, _cohen_d

logger = structlog.get_logger()
router = APIRouter()


@router.get(
    "/questionnaires", summary="All questionnaire responses with full Likert detail"
)
async def list_questionnaire_responses(
    session: AsyncSession = Depends(get_session),
    condition: Optional[ExperimentCondition] = Query(default=None),
    scenario_id: Optional[int] = Query(default=None, ge=1, le=4),
    valid_only: bool = Query(default=True),
    include_open_ended: bool = Query(default=True),
):
    """
    Returns all questionnaire responses with per-item Likert scores,
    computed mean, and optional open-ended answers. Supports filtering
    by condition, scenario, and validity.
    """
    stmt = select(QuestionnaireResponse)
    if condition:
        stmt = stmt.where(QuestionnaireResponse.condition == condition)
    if scenario_id:
        stmt = stmt.where(QuestionnaireResponse.scenario_id == scenario_id)
    if valid_only:
        stmt = stmt.where(QuestionnaireResponse.is_valid)
    stmt = stmt.order_by(QuestionnaireResponse.submitted_at)

    rows = (await session.exec(stmt)).all()

    def _serialize(q: QuestionnaireResponse) -> dict:
        out = {
            "response_id": str(q.id),
            "participant_id": q.participant_id,
            "scenario_id": q.scenario_id,
            "condition": q.condition.value,
            "condition_order": q.condition_order,
            "order_in_session": q.order_in_session,
            "likert": {
                "trust_overall": q.trust_overall,
                "risk_awareness": q.risk_awareness,
                "technical_soundness": q.technical_soundness,
                "balance": q.balance,
                "actionability": q.actionability,
                "completeness": q.completeness,
            },
            "mean_score": round(q.mean_score, 3),
            "time_to_complete_seconds": q.time_to_complete_seconds,
            "is_valid": q.is_valid,
            "quality_note": q.quality_note,
            "submitted_at": q.submitted_at.isoformat(),
        }
        if include_open_ended:
            out["open_ended"] = {
                "strengths": q.strengths,
                "concerns": q.concerns,
                "trust_reasoning": q.trust_reasoning,
                "persona_consistency": q.persona_consistency,
                "debate_value": q.debate_value,
                "most_convincing_persona": q.most_convincing_persona,
            }
        return out

    serialized = [_serialize(q) for q in rows]

    baseline = [q for q in rows if q.condition == ExperimentCondition.BASELINE]
    multi = [q for q in rows if q.condition == ExperimentCondition.MULTIAGENT]

    return {
        "total": len(rows),
        "by_condition": {
            "baseline": {
                "n": len(baseline),
                "mean_score": _safe_mean([q.mean_score for q in baseline]),
            },
            "multiagent": {
                "n": len(multi),
                "mean_score": _safe_mean([q.mean_score for q in multi]),
            },
            "effect_size": _cohen_d(
                [q.mean_score for q in multi],
                [q.mean_score for q in baseline],
            ),
        },
        "responses": serialized,
    }
