"""
Experiment Exit Surveys - Exit survey endpoints.

GET /experiment-data/exit-surveys
"""

import structlog
from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session
from app.models.exit_survey import ExitSurvey
from app.models.participant import Participant

from app.api.v1.endpoints.experiment.experiment_helpers import _safe_mean

logger = structlog.get_logger()
router = APIRouter()


@router.get(
    "/exit-surveys", summary="All exit survey records with preference resolution"
)
async def list_exit_surveys(
    session: AsyncSession = Depends(get_session),
):
    """
    Returns all exit surveys with the resolved preferred_system_actual label,
    preference counts, and open-ended reasoning.
    """
    surveys = (await session.exec(select(ExitSurvey))).all()
    participants = {p.id: p for p in (await session.exec(select(Participant))).all()}

    def _serialize(s: ExitSurvey) -> dict:
        p = participants.get(s.participant_id)
        return {
            "survey_id": str(s.id),
            "participant_id": s.participant_id,
            "condition_order": (p.assigned_condition_order.value if p else None),
            "preference": {
                "raw": s.preferred_system.value,
                "actual": s.preferred_system_actual,
                "reasoning": s.preference_reasoning,
                "has_clear_preference": s.has_clear_preference,
            },
            "ratings": {
                "interface_rating": s.interface_rating,
                "experienced_fatigue": s.experienced_fatigue.value,
            },
            "feedback": {
                "technical_issues": s.technical_issues,
                "additional_feedback": s.additional_feedback,
            },
            "submitted_at": s.submitted_at.isoformat(),
        }

    serialized = [_serialize(s) for s in surveys]

    pref_counts = {"baseline": 0, "multiagent": 0, "no_preference": 0, "not_sure": 0}
    for s in surveys:
        key = s.preferred_system_actual or s.preferred_system.value
        if key in pref_counts:
            pref_counts[key] += 1

    interface_ratings = [s.interface_rating for s in surveys]
    fatigue_dist = {}
    for s in surveys:
        fatigue_dist[s.experienced_fatigue.value] = (
            fatigue_dist.get(s.experienced_fatigue.value, 0) + 1
        )

    return {
        "total": len(surveys),
        "preference_counts": pref_counts,
        "aggregate": {
            "mean_interface_rating": _safe_mean([float(r) for r in interface_ratings]),
            "fatigue_distribution": fatigue_dist,
        },
        "surveys": serialized,
    }
