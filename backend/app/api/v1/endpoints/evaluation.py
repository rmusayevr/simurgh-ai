"""
Evaluation endpoints for thesis questionnaire data collection.

Provides:
    - Submit questionnaire responses (RQ1: Trust, RQ3: Consensus)
    - List responses (researcher view)
    - Flag invalid responses
    - Export data for statistical analysis

Used for thesis A/B testing evaluation.
"""

import structlog
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session, get_current_user
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.user import User
from app.models.participant import Participant
from app.schemas.questionnaire import (
    QuestionnaireCreate,
    QuestionnaireRead,
    QuestionnaireListRead,
    QuestionnaireUpdate,
    QuestionnaireExportSummary,
)
from app.services.questionnaire_service import QuestionnaireService

logger = structlog.get_logger()
router = APIRouter()


# ==================== Submit Response ====================


@router.post("/responses", response_model=QuestionnaireRead, status_code=201)
async def submit_questionnaire(
    questionnaire_data: QuestionnaireCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Submit a questionnaire response.

    Participants submit one response per proposal condition (baseline/multiagent).

    Args:
        questionnaire_data: Questionnaire response data

    Returns:
        QuestionnaireRead: Submitted response

    Raises:
        BadRequestException: If validation fails
    """
    log = logger.bind(
        operation="submit_questionnaire",
        user_id=current_user.id,
        participant_id=questionnaire_data.participant_id,
        scenario_id=questionnaire_data.scenario_id,
    )

    participant = await session.get(Participant, questionnaire_data.participant_id)
    if not participant:
        log.error("questionnaire_participant_not_found")
        raise NotFoundException(
            f"Participant {questionnaire_data.participant_id} not found. "
            "Complete registration at /experiment/register first."
        )
    if participant.user_id != current_user.id:
        log.error(
            "questionnaire_ownership_mismatch",
            owner_user_id=participant.user_id,
        )
        raise BadRequestException(
            "Cannot submit questionnaire for another participant."
        )

    questionnaire_service = QuestionnaireService(session)

    try:
        response = await questionnaire_service.submit_response(questionnaire_data)
        log.info("questionnaire_submitted", response_id=response.id)
        return response

    except BadRequestException:
        raise
    except Exception as e:
        log.error("questionnaire_submission_failed", error=str(e), exc_info=True)
        raise BadRequestException(f"Failed to submit questionnaire: {str(e)}")


# ==================== List Responses ====================


@router.get("/responses", response_model=List[QuestionnaireListRead])
async def list_questionnaire_responses(
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
    scenario_id: Optional[int] = Query(default=None, ge=1, le=4),
    valid_only: bool = Query(default=True),
):
    """
    List questionnaire responses (researcher view).

    Args:
        scenario_id: Filter by scenario (1-4)
        valid_only: Only return valid (non-flagged) responses

    Returns:
        List[QuestionnaireListRead]: Response list
    """
    questionnaire_service = QuestionnaireService(session)

    if scenario_id:
        responses = await questionnaire_service.get_scenario_responses(
            scenario_id=scenario_id,
            valid_only=valid_only,
        )
    else:
        responses = await questionnaire_service.get_all_responses(valid_only=valid_only)

    return responses


@router.get("/responses/{response_id}", response_model=QuestionnaireRead)
async def get_questionnaire_response(
    response_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Get a single questionnaire response.

    Args:
        response_id: Response UUID

    Returns:
        QuestionnaireRead: Full response with open-ended answers

    Raises:
        NotFoundException: If response not found
    """
    questionnaire_service = QuestionnaireService(session)
    response = await questionnaire_service.get_response_by_id(response_id)
    return response


# ==================== Update/Flag Responses ====================


@router.patch("/responses/{response_id}", response_model=QuestionnaireRead)
async def update_questionnaire_response(
    response_id: UUID,
    update_data: QuestionnaireUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Update questionnaire metadata (researcher only).

    Used to flag invalid responses or add quality notes.

    Args:
        response_id: Response UUID
        update_data: Fields to update (is_valid, quality_note)

    Returns:
        QuestionnaireRead: Updated response

    Raises:
        NotFoundException: If response not found
    """
    questionnaire_service = QuestionnaireService(session)

    response = await questionnaire_service.update_response(
        response_id=response_id,
        data=update_data,
    )

    logger.info("questionnaire_updated", response_id=str(response_id))
    return response


@router.post("/responses/{response_id}/flag")
async def flag_invalid_response(
    response_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    reason: str = Query(..., min_length=5, max_length=500),
    session: AsyncSession = Depends(get_session),
):
    """
    Flag a response as invalid (exclude from analysis).

    Used to exclude incomplete, suspicious, or low-quality responses.

    Args:
        response_id: Response UUID
        reason: Reason for invalidation

    Returns:
        dict: Success message

    Raises:
        NotFoundException: If response not found
    """
    questionnaire_service = QuestionnaireService(session)

    await questionnaire_service.flag_invalid(
        response_id=response_id,
        reason=reason,
    )

    logger.info("response_flagged_invalid", response_id=str(response_id), reason=reason)

    return {
        "success": True,
        "message": "Response flagged as invalid",
    }


# ==================== Statistics & Export ====================


@router.get("/statistics")
async def get_questionnaire_statistics(
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
    scenario_id: Optional[int] = Query(default=None, ge=1, le=4),
):
    """
    Get summary statistics for questionnaire responses.

    Calculates:
    - Mean scores by condition (baseline vs multiagent)
    - Effect sizes (Cohen's d)
    - Sample sizes

    Used for thesis Chapter 5 reporting.

    Args:
        scenario_id: Optional filter by scenario

    Returns:
        dict: Summary statistics
    """
    questionnaire_service = QuestionnaireService(session)

    stats = await questionnaire_service.calculate_summary_statistics(
        scenario_id=scenario_id,
        valid_only=False,
    )

    return stats


@router.get("/export", response_model=QuestionnaireExportSummary)
async def export_questionnaire_data(
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
    valid_only: bool = Query(default=True),
):
    """
    Export all questionnaire data for statistical analysis.

    Returns CSV-ready flat data with summary statistics.
    Used for SPSS/R analysis in thesis Chapter 5.

    Args:
        valid_only: Only export valid responses

    Returns:
        QuestionnaireExportSummary: Export data + summary stats
    """
    questionnaire_service = QuestionnaireService(session)

    export_data = await questionnaire_service.export_all_responses(
        valid_only=valid_only
    )

    logger.info("questionnaire_data_exported", total_rows=export_data.total_responses)

    return export_data
