"""
Exit Survey endpoint for thesis post-experiment data collection.

Provides:
    POST /experiment/exit-survey  — Submit exit survey (one per participant)
    GET  /experiment/exit-survey/me — Retrieve own survey (idempotency check)

Thesis Context:
    Data feeds Chapter 5 Section 5.3.3 ("Participant Preferences").
    Also marks the participant's completed_at timestamp, signalling the
    full experiment is done.

Critical Design Constraint:
    The debrief text mapping condition labels (Condition A = baseline,
    Condition B = multi-agent) is rendered exclusively on the FRONTEND
    AFTER the response is persisted. This endpoint must never return
    condition label mappings, preserving preference-data integrity.
"""

import structlog
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session, get_current_user
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
)
from app.models.user import User
from app.models.participant import Participant
from app.models.exit_survey import ExitSurvey
from app.schemas.exit_survey import ExitSurveyCreate, ExitSurveyRead

logger = structlog.get_logger()
router = APIRouter()


# ==================== Submit Exit Survey ====================


@router.post("/exit-survey", response_model=ExitSurveyRead, status_code=201)
async def submit_exit_survey(
    survey_data: ExitSurveyCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Submit the post-experiment exit survey.

    Must be called once after the second TrustQuestionnaire is submitted.
    Idempotent: returns the existing record if the participant already submitted.

    Side-effects:
        - Creates ExitSurvey record
        - Sets participant.completed_at (marks experiment as done)

    Raises:
        NotFoundException: If participant record not found
        BadRequestException: If participant_id does not belong to current user
    """
    log = logger.bind(
        operation="submit_exit_survey",
        user_id=current_user.id,
        participant_id=survey_data.participant_id,
    )

    # ── Verify participant exists and belongs to this user ─────────────────
    participant = await session.get(Participant, survey_data.participant_id)
    if not participant:
        raise NotFoundException(f"Participant {survey_data.participant_id} not found.")
    if participant.user_id != current_user.id:
        raise BadRequestException("Cannot submit exit survey for another participant.")

    # ── Idempotency: return existing record if already submitted ───────────
    existing_result = await session.exec(
        select(ExitSurvey).where(
            ExitSurvey.participant_id == survey_data.participant_id
        )
    )
    existing = existing_result.first()
    if existing:
        log.info("exit_survey_already_submitted", survey_id=str(existing.id))
        return existing

    # ── Create exit survey record ──────────────────────────────────────────
    survey = ExitSurvey(
        participant_id=survey_data.participant_id,
        preferred_system=survey_data.preferred_system,
        preferred_system_actual=survey_data.preferred_system_actual,
        preference_reasoning=survey_data.preference_reasoning,
        interface_rating=survey_data.interface_rating,
        experienced_fatigue=survey_data.experienced_fatigue,
        technical_issues=survey_data.technical_issues or None,
        additional_feedback=survey_data.additional_feedback or None,
    )

    session.add(survey)

    # ── Mark participant as completed ──────────────────────────────────────
    if not participant.completed_at:
        participant.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(participant)

    await session.commit()
    await session.refresh(survey)

    log.info(
        "exit_survey_submitted",
        survey_id=str(survey.id),
        preferred_system=survey.preferred_system.value,
        interface_rating=survey.interface_rating,
        participant_completed=True,
    )

    return survey


# ==================== Get Own Exit Survey ====================


@router.get("/exit-survey/me", response_model=ExitSurveyRead)
async def get_my_exit_survey(
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Retrieve the current user's exit survey (if already submitted).

    Used for idempotency checks on page refresh.

    Raises:
        NotFoundException: If no exit survey exists yet for this user
    """
    # Resolve participant for this user
    participant_result = await session.exec(
        select(Participant).where(Participant.user_id == current_user.id)
    )
    participant = participant_result.first()
    if not participant:
        raise NotFoundException("No participant record found.")

    survey_result = await session.exec(
        select(ExitSurvey).where(ExitSurvey.participant_id == participant.id)
    )
    survey = survey_result.first()
    if not survey:
        raise NotFoundException("No exit survey submitted yet.")

    return survey
