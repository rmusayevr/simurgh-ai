"""
Experiment Management - Reset and delete endpoints.

DELETE /experiment-data/reset
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, Query
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session, get_current_superuser
from app.core.exceptions import BadRequestException
from app.models.user import User
from app.models.participant import Participant
from app.models.questionnaire import QuestionnaireResponse
from app.models.debate import DebateSession
from app.models.exit_survey import ExitSurvey
from app.models.persona_coding import PersonaCoding

logger = structlog.get_logger()
router = APIRouter()


@router.delete(
    "/reset",
    summary="⚠️  Wipe all experiment data — irreversible",
    status_code=200,
)
async def reset_all_experiment_data(
    confirm: str = Query(
        ...,
        description="Must be exactly 'CONFIRM_RESET' to proceed",
    ),
    keep_participants: bool = Query(
        default=False,
        description="If true, preserve Participant and User records; only delete responses",
    ),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_superuser),
):
    """
    **Irreversibly deletes** all experiment response data.

    What gets deleted (in cascade order):
    - PersonaCoding records
    - ExitSurvey records
    - QuestionnaireResponse records
    - DebateSession records (and their debate_history JSON)
    - Participant records (unless keep_participants=true)

    Proposal, Project, and User accounts are **never** touched.

    Requires the query param `confirm=CONFIRM_RESET` as a safety gate.
    """
    if confirm != "CONFIRM_RESET":
        raise BadRequestException(
            "Confirmation required. Pass ?confirm=CONFIRM_RESET to proceed."
        )

    log = logger.bind(
        operation="reset_experiment_data",
        requested_by=current_user.email,
        keep_participants=keep_participants,
    )

    counts_before = {
        "participants": (
            await session.exec(select(func.count()).select_from(Participant))
        ).one(),
        "questionnaires": (
            await session.exec(select(func.count()).select_from(QuestionnaireResponse))
        ).one(),
        "debates": (
            await session.exec(select(func.count()).select_from(DebateSession))
        ).one(),
        "exit_surveys": (
            await session.exec(select(func.count()).select_from(ExitSurvey))
        ).one(),
        "persona_codings": (
            await session.exec(select(func.count()).select_from(PersonaCoding))
        ).one(),
    }

    for coding in (await session.exec(select(PersonaCoding))).all():
        await session.delete(coding)

    for survey in (await session.exec(select(ExitSurvey))).all():
        await session.delete(survey)

    for qr in (await session.exec(select(QuestionnaireResponse))).all():
        await session.delete(qr)

    for debate in (await session.exec(select(DebateSession))).all():
        await session.delete(debate)

    if not keep_participants:
        for participant in (await session.exec(select(Participant))).all():
            await session.delete(participant)

    await session.commit()

    log.warning("experiment_data_reset_complete", counts_before=counts_before)

    return {
        "success": True,
        "reset_at": datetime.now(timezone.utc).isoformat(),
        "requested_by": current_user.email,
        "keep_participants": keep_participants,
        "records_deleted": counts_before,
        "note": (
            "Participant records preserved. "
            "Use keep_participants=false to delete them too."
            if keep_participants
            else "All experiment data wiped. Participant records deleted too."
        ),
    }
