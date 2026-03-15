"""
Experiments endpoints for thesis A/B testing.

Provides:
    - POST /register: Participant consent + demographics registration
    - GET  /participant/me: Retrieve own participant record (resume on refresh)
    - GET  /participant/{id}: Retrieve participant by ID
    - POST /baseline: Generate single-agent baseline proposals for Condition A
    - GET  /compare/{proposal_id}: Compare baseline vs multi-agent metrics
    - GET  /conditions: Metadata about Condition A vs B

Used for thesis experimental design (Condition A vs Condition B).
"""

import structlog
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session, get_current_user
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.models.participant import Participant, ConditionOrder
from app.schemas.participant import ParticipantCreate, ParticipantRead

logger = structlog.get_logger()
router = APIRouter()


# ==================== Participant Registration ====================


@router.post("/register", response_model=ParticipantRead, status_code=201)
async def register_participant(
    registration_data: ParticipantCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Register the current user as a research participant.

    Creates a Participant record with verified consent, demographics,
    and a randomly assigned condition order (50/50 counterbalancing).

    Idempotent: returns the existing record if the user already registered.

    Raises:
        422: If consent_given is False (schema validation)
    """
    log = logger.bind(operation="register_participant", user_id=current_user.id)

    # Idempotency — return existing record if already registered
    existing_result = await session.exec(
        select(Participant).where(Participant.user_id == current_user.id)
    )
    existing = existing_result.first()
    if existing:
        log.info("participant_already_registered", participant_id=existing.id)
        return existing

    participant = Participant(
        user_id=current_user.id,
        experience_level=registration_data.experience_level,
        years_experience=registration_data.years_experience,
        familiarity_with_ai=registration_data.familiarity_with_ai,
        consent_given=registration_data.consent_given,
        consent_timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        assigned_condition_order=ConditionOrder.random(),
    )

    session.add(participant)
    await session.commit()
    await session.refresh(participant)

    log.info(
        "participant_registered",
        participant_id=participant.id,
        condition_order=participant.assigned_condition_order.value,
    )
    return participant


@router.get("/participant/me", response_model=ParticipantRead)
async def get_my_participant_record(
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Retrieve the current user's participant record.

    Used on page refresh to resume experiment without losing condition assignment.

    Raises:
        NotFoundException: If user has not yet registered as a participant
    """
    result = await session.exec(
        select(Participant).where(Participant.user_id == current_user.id)
    )
    participant = result.first()
    if not participant:
        raise NotFoundException(
            "No participant record found. "
            "Please complete registration at /experiment/register."
        )
    return participant


@router.get("/participant/{participant_id}", response_model=ParticipantRead)
async def get_participant(
    participant_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """Retrieve a participant record by ID."""
    participant = await session.get(Participant, participant_id)
    if not participant:
        raise NotFoundException(f"Participant {participant_id} not found")
    return participant
