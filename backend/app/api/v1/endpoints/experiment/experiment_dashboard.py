"""
Experiment Dashboard - Study-level overview metrics.

GET /experiment-data/overview
"""

import structlog
from fastapi import APIRouter, Depends
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session
from app.models.participant import Participant, ConditionOrder
from app.models.questionnaire import QuestionnaireResponse, ExperimentCondition
from app.models.debate import DebateSession
from app.models.exit_survey import ExitSurvey, PreferredSystem
from app.models.persona_coding import PersonaCoding

from app.api.v1.endpoints.experiment.experiment_helpers import _safe_mean

logger = structlog.get_logger()
router = APIRouter()


@router.get("/overview", summary="Study-level dashboard metrics")
async def get_experiment_overview(
    session: AsyncSession = Depends(get_session),
):
    """
    Returns a high-level snapshot of the entire study:
    participant counts, completion rates, data quality flags,
    and a quick per-condition mean trust score.
    """
    total_participants = (
        await session.exec(select(func.count()).select_from(Participant))
    ).one()

    completed_participants = (
        await session.exec(
            select(func.count())
            .select_from(Participant)
            .where(Participant.completed_at.isnot(None))
        )
    ).one()

    total_questionnaires = (
        await session.exec(select(func.count()).select_from(QuestionnaireResponse))
    ).one()

    valid_questionnaires = (
        await session.exec(
            select(func.count())
            .select_from(QuestionnaireResponse)
            .where(QuestionnaireResponse.is_valid)
        )
    ).one()

    total_debates = (
        await session.exec(select(func.count()).select_from(DebateSession))
    ).one()

    consensus_debates = (
        await session.exec(
            select(func.count())
            .select_from(DebateSession)
            .where(DebateSession.consensus_reached)
        )
    ).one()

    total_exit_surveys = (
        await session.exec(select(func.count()).select_from(ExitSurvey))
    ).one()

    total_codings = (
        await session.exec(select(func.count()).select_from(PersonaCoding))
    ).one()

    baseline_first = (
        await session.exec(
            select(func.count())
            .select_from(Participant)
            .where(
                Participant.assigned_condition_order == ConditionOrder.BASELINE_FIRST
            )
        )
    ).one()

    multiagent_first = (
        await session.exec(
            select(func.count())
            .select_from(Participant)
            .where(
                Participant.assigned_condition_order == ConditionOrder.MULTIAGENT_FIRST
            )
        )
    ).one()

    q_rows = (
        await session.exec(
            select(QuestionnaireResponse).where(QuestionnaireResponse.is_valid)
        )
    ).all()

    baseline_scores = [
        r.mean_score for r in q_rows if r.condition == ExperimentCondition.BASELINE
    ]
    multi_scores = [
        r.mean_score for r in q_rows if r.condition == ExperimentCondition.MULTIAGENT
    ]

    exit_rows = (await session.exec(select(ExitSurvey))).all()
    pref_baseline = sum(1 for e in exit_rows if e.preferred_system_actual == "baseline")
    pref_multi = sum(1 for e in exit_rows if e.preferred_system_actual == "multiagent")
    pref_none = sum(
        1
        for e in exit_rows
        if e.preferred_system
        in (PreferredSystem.NO_PREFERENCE, PreferredSystem.NOT_SURE)
    )

    return {
        "participants": {
            "total": total_participants,
            "completed": completed_participants,
            "completion_rate_pct": round(
                (completed_participants / total_participants * 100)
                if total_participants
                else 0,
                1,
            ),
            "condition_balance": {
                "baseline_first": baseline_first,
                "multiagent_first": multiagent_first,
            },
        },
        "questionnaires": {
            "total": total_questionnaires,
            "valid": valid_questionnaires,
            "validity_rate_pct": round(
                (valid_questionnaires / total_questionnaires * 100)
                if total_questionnaires
                else 0,
                1,
            ),
            "mean_trust_score": {
                "baseline": _safe_mean(baseline_scores),
                "multiagent": _safe_mean(multi_scores),
            },
        },
        "debates": {
            "total": total_debates,
            "consensus_reached": consensus_debates,
            "consensus_rate_pct": round(
                (consensus_debates / total_debates * 100) if total_debates else 0, 1
            ),
        },
        "exit_surveys": {
            "total": total_exit_surveys,
            "preferred_baseline": pref_baseline,
            "preferred_multiagent": pref_multi,
            "no_preference_or_unsure": pref_none,
        },
        "rq2_persona_codings": {
            "total_codings": total_codings,
        },
    }
