"""
Experiment Participants - Participant management endpoints.

GET /experiment-data/participants
GET /experiment-data/participants/{participant_id}
PATCH /experiment-data/participants/{participant_id}/invalidate
DELETE /experiment-data/participants/{participant_id}
"""

import structlog
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.models.participant import Participant, ConditionOrder
from app.models.questionnaire import QuestionnaireResponse, ExperimentCondition
from app.models.exit_survey import ExitSurvey
from app.models.debate import DebateSession

from app.api.v1.endpoints.experiment.experiment_helpers import _safe_mean

logger = structlog.get_logger()
router = APIRouter()


def _build_participant_status(p: Participant, surveys: dict, q_map: dict) -> dict:
    """Return a concise progress object for a participant."""
    qs = q_map.get(p.id, [])
    baseline_q = [r for r in qs if r.condition == ExperimentCondition.BASELINE]
    multi_q = [r for r in qs if r.condition == ExperimentCondition.MULTIAGENT]
    survey = surveys.get(p.id)
    steps_done = bool(baseline_q) + bool(multi_q) + bool(survey)
    return {
        "questionnaire_baseline_done": bool(baseline_q),
        "questionnaire_multiagent_done": bool(multi_q),
        "exit_survey_done": bool(survey),
        "steps_completed": steps_done,
        "steps_total": 3,
        "is_fully_complete": p.is_completed,
    }


@router.get("/participants", summary="All participants with full progress detail")
async def list_participants(
    session: AsyncSession = Depends(get_session),
    completed_only: bool = Query(default=False),
    condition_order: Optional[ConditionOrder] = Query(default=None),
):
    """
    Returns every participant joined with their user account, questionnaire
    progress, and exit survey status. Supports filtering by completion or
    condition order.
    """
    stmt = select(Participant)
    if completed_only:
        stmt = stmt.where(Participant.completed_at.isnot(None))
    if condition_order:
        stmt = stmt.where(Participant.assigned_condition_order == condition_order)
    stmt = stmt.order_by(Participant.created_at)

    participants = (await session.exec(stmt)).all()

    all_q = (await session.exec(select(QuestionnaireResponse))).all()
    q_map: dict[int, list[QuestionnaireResponse]] = {}
    for q in all_q:
        q_map.setdefault(q.participant_id, []).append(q)

    all_surveys = (await session.exec(select(ExitSurvey))).all()
    survey_map = {s.participant_id: s for s in all_surveys}

    all_users = (await session.exec(select(User))).all()
    user_map = {u.id: u for u in all_users}

    results = []
    for p in participants:
        user = user_map.get(p.user_id)
        qs = q_map.get(p.id, [])
        survey = survey_map.get(p.id)

        baseline_qs = [r for r in qs if r.condition == ExperimentCondition.BASELINE]
        multi_qs = [r for r in qs if r.condition == ExperimentCondition.MULTIAGENT]

        results.append(
            {
                "participant_id": p.id,
                "user": {
                    "id": p.user_id,
                    "email": user.email if user else None,
                    "full_name": user.full_name if user else None,
                },
                "demographics": {
                    "experience_level": p.experience_level.value,
                    "years_experience": p.years_experience,
                    "familiarity_with_ai": p.familiarity_with_ai,
                },
                "experiment": {
                    "assigned_condition_order": p.assigned_condition_order.value,
                    "consent_given": p.consent_given,
                    "consent_timestamp": (
                        p.consent_timestamp.isoformat() if p.consent_timestamp else None
                    ),
                    "registered_at": p.created_at.isoformat(),
                    "completed_at": (
                        p.completed_at.isoformat() if p.completed_at else None
                    ),
                    "duration_minutes": (
                        round((p.completed_at - p.created_at).total_seconds() / 60, 1)
                        if p.completed_at
                        else None
                    ),
                },
                "progress": _build_participant_status(p, survey_map, q_map),
                "questionnaire_summary": {
                    "baseline": {
                        "submitted": bool(baseline_qs),
                        "mean_score": _safe_mean([r.mean_score for r in baseline_qs]),
                        "trust_overall": (
                            baseline_qs[0].trust_overall if baseline_qs else None
                        ),
                        "scenario_id": (
                            baseline_qs[0].scenario_id if baseline_qs else None
                        ),
                        "is_valid": baseline_qs[0].is_valid if baseline_qs else None,
                    },
                    "multiagent": {
                        "submitted": bool(multi_qs),
                        "mean_score": _safe_mean([r.mean_score for r in multi_qs]),
                        "trust_overall": multi_qs[0].trust_overall
                        if multi_qs
                        else None,
                        "scenario_id": multi_qs[0].scenario_id if multi_qs else None,
                        "is_valid": multi_qs[0].is_valid if multi_qs else None,
                    },
                },
                "exit_survey": {
                    "completed": bool(survey),
                    "preferred_system": (
                        survey.preferred_system_actual if survey else None
                    ),
                },
            }
        )

    return {
        "total": len(results),
        "participants": results,
    }


@router.get("/participants/{participant_id}", summary="Full detail for one participant")
async def get_participant_detail(
    participant_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Returns full detail for a single participant: user info, demographics,
    all questionnaire responses, exit survey, and any debate sessions they ran.
    """
    participant = await session.get(Participant, participant_id)
    if not participant:
        raise NotFoundException(f"Participant {participant_id} not found")

    user = await session.get(User, participant.user_id)

    q_stmt = select(QuestionnaireResponse).where(
        QuestionnaireResponse.participant_id == participant_id
    )
    questionnaires = (await session.exec(q_stmt)).all()

    survey_stmt = select(ExitSurvey).where(ExitSurvey.participant_id == participant_id)
    survey_result = (await session.exec(survey_stmt)).first()

    return {
        "participant_id": participant.id,
        "user": {
            "id": user.id if user else participant.user_id,
            "email": user.email if user else None,
            "full_name": user.full_name if user else None,
        },
        "demographics": {
            "experience_level": participant.experience_level.value,
            "years_experience": participant.years_experience,
            "familiarity_with_ai": participant.familiarity_with_ai,
        },
        "experiment": {
            "assigned_condition_order": participant.assigned_condition_order.value,
            "consent_given": participant.consent_given,
            "consent_timestamp": (
                participant.consent_timestamp.isoformat()
                if participant.consent_timestamp
                else None
            ),
            "registered_at": participant.created_at.isoformat(),
            "completed_at": (
                participant.completed_at.isoformat()
                if participant.completed_at
                else None
            ),
            "is_completed": participant.is_completed,
            "duration_minutes": (
                round(
                    (participant.completed_at - participant.created_at).total_seconds()
                    / 60,
                    1,
                )
                if participant.completed_at
                else None
            ),
        },
        "questionnaires": [
            {
                "response_id": str(q.id),
                "condition": q.condition.value,
                "scenario_id": q.scenario_id,
                "order_in_session": q.order_in_session,
                "mean_score": round(q.mean_score, 3),
                "likert_scores": {
                    "trust_overall": q.trust_overall,
                    "risk_awareness": q.risk_awareness,
                    "technical_soundness": q.technical_soundness,
                    "balance": q.balance,
                    "actionability": q.actionability,
                    "completeness": q.completeness,
                },
                "open_ended": {
                    "strengths": q.strengths,
                    "concerns": q.concerns,
                    "trust_reasoning": q.trust_reasoning,
                    "persona_consistency": q.persona_consistency,
                    "debate_value": q.debate_value,
                    "most_convincing_persona": q.most_convincing_persona,
                },
                "metadata": {
                    "time_to_complete_seconds": q.time_to_complete_seconds,
                    "is_valid": q.is_valid,
                    "quality_note": q.quality_note,
                    "submitted_at": q.submitted_at.isoformat(),
                },
            }
            for q in questionnaires
        ],
        "exit_survey": (
            {
                "survey_id": str(survey_result.id),
                "preferred_system_raw": survey_result.preferred_system.value,
                "preferred_system_actual": survey_result.preferred_system_actual,
                "preference_reasoning": survey_result.preference_reasoning,
                "interface_rating": survey_result.interface_rating,
                "experienced_fatigue": survey_result.experienced_fatigue.value,
                "technical_issues": survey_result.technical_issues,
                "additional_feedback": survey_result.additional_feedback,
                "submitted_at": survey_result.submitted_at.isoformat(),
            }
            if survey_result
            else None
        ),
    }


@router.patch(
    "/participants/{participant_id}/invalidate",
    summary="Flag participant data as invalid",
)
async def invalidate_participant(
    participant_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Flags all of a participant's questionnaire responses as invalid.
    Does NOT delete the records — makes them invalid for analysis.
    """
    participant = await session.get(Participant, participant_id)
    if not participant:
        raise NotFoundException(f"Participant {participant_id} not found")

    q_stmt = select(QuestionnaireResponse).where(
        QuestionnaireResponse.participant_id == participant_id
    )
    questionnaires = (await session.exec(q_stmt)).all()

    invalidated = 0
    for q in questionnaires:
        q.is_valid = False
        q.quality_note = "Manually invalidated at"
        invalidated += 1

    await session.commit()

    logger.info(
        "participant_invalidated", participant_id=participant_id, count=invalidated
    )

    return {
        "success": True,
        "participant_id": participant_id,
        "invalidated_count": invalidated,
    }


@router.delete(
    "/participants/{participant_id}",
    summary="Delete a single participant and all their data",
    status_code=200,
)
async def delete_participant(
    participant_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Irreversibly deletes a participant and ALL their associated data:
    questionnaire responses, exit surveys, debate sessions, and the
    participant record itself.
    """
    participant = await session.get(Participant, participant_id)
    if not participant:
        raise NotFoundException(f"Participant {participant_id} not found")

    for q in (
        await session.exec(
            select(QuestionnaireResponse).where(
                QuestionnaireResponse.participant_id == participant_id
            )
        )
    ).all():
        await session.delete(q)

    for s in (
        await session.exec(
            select(ExitSurvey).where(ExitSurvey.participant_id == participant_id)
        )
    ).all():
        await session.delete(s)

    for d in (
        await session.exec(
            select(DebateSession).where(DebateSession.proposal_id == participant_id)
        )
    ).all():
        await session.delete(d)

    await session.delete(participant)
    await session.commit()

    logger.warning("participant_deleted", participant_id=participant_id)

    return {
        "success": True,
        "deleted_participant_id": participant_id,
    }
