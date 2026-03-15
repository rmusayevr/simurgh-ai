"""
Debate endpoints for multi-agent council debates.

Provides:
    - Start debate for a proposal
    - Get debate history and details
    - List debates for a proposal
    - Get debate metrics (RQ2: persona consistency, RQ3: consensus efficiency)

Thesis integration:
    - RQ2: Persona consistency tracking per turn
    - RQ3: Consensus efficiency metrics (turns, duration, conflict density)

Debate workflow:
    1. Proposal created → Execute proposal → Triggers debate
    2. Council debates (3 personas: Legacy Keeper, Innovator, Mediator)
    3. Consensus reached or max turns exceeded
    4. Final proposal generated from synthesis
    5. Metrics stored in DebateSession
"""

import structlog
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session, get_current_user
from app.core.exceptions import NotFoundException, BadRequestException
from app.models.user import User
from app.schemas.debate import (
    DebateSessionRead,
    DebateSessionDetail,
    DebateTurnRead,
    StartDebateRequest,
)
from app.services.debate_service import DebateService

logger = structlog.get_logger()
router = APIRouter()


# ==================== Frontend-Facing Endpoints ====================
# These match the URL patterns used by the frontend debateApi client:
#   POST /debates/proposals/{id}/start_debate
#   GET  /debates/proposals/{id}/history
#
# ROUTE ORDER: /proposals/{id}/start_debate and /proposals/{id}/history
# must be registered BEFORE /{debate_id} to avoid UUID parse errors.


@router.post("/proposals/{proposal_id}/start_debate", response_model=DebateSessionRead)
async def start_debate(
    proposal_id: int,
    payload: StartDebateRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Start a multi-agent council debate for a proposal.

    Runs the full debate synchronously (Legacy Keeper → Innovator → Mediator
    in rotation, up to max_turns rounds) and returns the completed session.

    Args:
        proposal_id: Proposal to debate
        payload: Optional document IDs and focus areas

    Returns:
        DebateSessionRead: Completed debate with all turns and metrics

    Raises:
        NotFoundException: If proposal not found
        BadRequestException: If proposal is not in COMPLETED state
    """
    log = logger.bind(operation="start_debate", proposal_id=proposal_id)

    debate_service = DebateService(session)

    try:
        debate = await debate_service.conduct_debate(
            proposal_id=proposal_id,
            user_id=current_user.id,
            user_role=current_user.role,
        )
    except (NotFoundException, BadRequestException):
        raise
    except Exception as exc:
        log.error("debate_failed", error=str(exc))
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail=f"Debate failed: {exc}") from exc

    log.info("debate_started", debate_id=str(debate.id))
    return debate


@router.get("/proposals/{proposal_id}/history", response_model=DebateSessionRead)
async def get_proposal_debate_history(
    proposal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Get the latest debate session for a proposal (history view).

    This is the primary endpoint the frontend uses to load an existing
    debate after navigating back to the War Room.

    Args:
        proposal_id: Proposal ID

    Returns:
        DebateSessionRead: Most recent debate session

    Raises:
        NotFoundException: If no debates found for this proposal
    """
    from sqlmodel import select
    from app.models.debate import DebateSession

    result = await session.exec(
        select(DebateSession)
        .where(DebateSession.proposal_id == proposal_id)
        .order_by(DebateSession.started_at.desc())
        .limit(1)
    )
    debate = result.first()

    if not debate:
        raise NotFoundException(f"No debate found for proposal {proposal_id}")

    # Verify access via the debate service helper
    debate_service = DebateService(session)
    await debate_service._get_proposal_with_access(
        proposal_id, current_user.id, current_user.role
    )

    return debate


# ==================== Synthesize Proposals ====================
@router.post("/{debate_id}/synthesize")
async def synthesize_proposals(
    debate_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Generate (or regenerate) the final consensus proposal for a debate.

    Runs _generate_final_proposal() which sends the full debate transcript
    to Claude and synthesises it into 3 implementation paths. The result is
    persisted on the DebateSession and returned to the frontend.

    Args:
        debate_id: Debate session UUID

    Returns:
        dict: { final_proposal: str, debate_id: str, status: str }

    Raises:
        NotFoundException: If debate not found or user lacks access
    """
    from sqlalchemy.orm.attributes import flag_modified

    debate_service = DebateService(session)

    # Fetch debate with access control
    debate = await debate_service.get_debate_by_id(
        debate_id=debate_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    # Fetch the parent proposal for context
    from app.models.proposal import Proposal

    proposal = await session.get(Proposal, debate.proposal_id)
    if not proposal:
        raise NotFoundException(f"Proposal {debate.proposal_id} not found")

    logger.info("synthesize_proposals_started", debate_id=str(debate_id))

    # Delegate to the existing service method
    final_text = await debate_service._generate_final_proposal(debate, proposal)

    # Persist the synthesised proposal back onto the session
    debate.final_consensus_proposal = final_text
    flag_modified(debate, "final_consensus_proposal")
    session.add(debate)
    await session.commit()

    logger.info(
        "synthesize_proposals_complete",
        debate_id=str(debate_id),
        length=len(final_text),
    )

    return {
        "status": "complete",
        "debate_id": str(debate_id),
        "final_proposal": final_text,
    }


# ==================== Get Debate ====================


@router.get("/{debate_id}", response_model=DebateSessionDetail)
async def get_debate(
    debate_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Get debate details including full turn history.

    Args:
        debate_id: Debate session UUID

    Returns:
        DebateSessionDetail: Full debate with turns and metrics

    Raises:
        NotFoundException: If debate not found or user lacks access
    """
    debate_service = DebateService(session)

    debate = await debate_service.get_debate_by_id(
        debate_id=debate_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    return DebateSessionDetail.from_session(debate)


@router.get("/proposal/{proposal_id}", response_model=List[DebateSessionRead])
@router.get("/proposals/{proposal_id}", response_model=List[DebateSessionRead])
async def list_proposal_debates(
    proposal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    List all debates for a proposal.

    Proposals can have multiple debate sessions if retried.

    Args:
        proposal_id: Proposal ID

    Returns:
        List[DebateSessionRead]: Debate sessions ordered by most recent

    Raises:
        ForbiddenException: If user lacks proposal access
    """
    debate_service = DebateService(session)

    debates = await debate_service.get_debates_by_proposal(
        proposal_id=proposal_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    return debates


@router.get("/proposal/{proposal_id}/latest", response_model=DebateSessionDetail)
async def get_latest_debate(
    proposal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Get the most recent debate for a proposal.

    Useful for displaying current debate status in UI.

    Args:
        proposal_id: Proposal ID

    Returns:
        DebateSessionDetail: Latest debate session

    Raises:
        NotFoundException: If no debates found or user lacks access
    """
    debate_service = DebateService(session)

    debates = await debate_service.get_debates_by_proposal(
        proposal_id=proposal_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    if not debates:
        raise NotFoundException(f"No debates found for proposal {proposal_id}")

    # Get full details for latest debate
    latest_debate = await debate_service.get_debate_by_id(
        debate_id=debates[0].id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    return DebateSessionDetail.from_session(latest_debate)


# ==================== Debate Metrics (Thesis RQ2/RQ3) ====================


@router.get("/{debate_id}/metrics")
async def get_debate_metrics(
    debate_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Get thesis metrics for a debate.

    Returns RQ2 and RQ3 metrics:
    - RQ2: Persona consistency scores (legacy keeper, innovator, mediator)
    - RQ3: Consensus efficiency (duration, turns, conflict density)

    Args:
        debate_id: Debate session UUID

    Returns:
        dict: Thesis metrics

    Raises:
        NotFoundException: If debate not found or user lacks access
    """
    debate_service = DebateService(session)

    # Get debate with access control
    debate = await debate_service.get_debate_by_id(
        debate_id=debate_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    metrics = {
        # RQ2: Persona Consistency
        "persona_consistency": {
            "legacy_keeper": debate.legacy_keeper_consistency,
            "innovator": debate.innovator_consistency,
            "mediator": debate.mediator_consistency,
            "overall": (
                (
                    (debate.legacy_keeper_consistency or 0)
                    + (debate.innovator_consistency or 0)
                    + (debate.mediator_consistency or 0)
                )
                / 3
                if any(
                    [
                        debate.legacy_keeper_consistency,
                        debate.innovator_consistency,
                        debate.mediator_consistency,
                    ]
                )
                else None
            ),
        },
        # RQ3: Consensus Efficiency
        "consensus_efficiency": {
            "total_turns": debate.total_turns,
            "duration_seconds": debate.duration_seconds,
            "conflict_density": debate.conflict_density,
            "consensus_reached": debate.consensus_reached,
        },
        # Additional context
        "debate_info": {
            "debate_id": str(debate.id),
            "proposal_id": debate.proposal_id,
            "completed_at": (
                debate.completed_at.isoformat() if debate.completed_at else None
            ),
        },
    }

    return metrics


@router.get("/{debate_id}/turns", response_model=List[DebateTurnRead])
async def get_debate_turns(
    debate_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Get all turns for a debate.

    Useful for detailed analysis and replay.

    Args:
        debate_id: Debate session UUID

    Returns:
        List[DebateTurnRead]: All debate turns in order

    Raises:
        NotFoundException: If debate not found or user lacks access
    """
    debate_service = DebateService(session)

    turns = await debate_service.get_debate_turns(
        debate_id=debate_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    return turns


# ==================== Analysis & Export ====================


@router.get("/proposal/{proposal_id}/summary")
async def get_debate_summary(
    proposal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Get aggregated debate summary for a proposal.

    Combines metrics across all debate sessions (if multiple retries).

    Args:
        proposal_id: Proposal ID

    Returns:
        dict: Aggregated metrics

    Raises:
        NotFoundException: If proposal not found or user lacks access
    """
    debate_service = DebateService(session)

    debates = await debate_service.get_debates_by_proposal(
        proposal_id=proposal_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    if not debates:
        raise NotFoundException(f"No debates found for proposal {proposal_id}")

    # Calculate aggregates
    total_sessions = len(debates)
    avg_turns = sum(d.total_turns for d in debates) / total_sessions
    avg_duration = sum(d.duration_seconds for d in debates) / total_sessions
    consensus_rate = sum(1 for d in debates if d.consensus_reached) / total_sessions

    # Persona consistency averages
    legacy_scores = [
        d.legacy_keeper_consistency for d in debates if d.legacy_keeper_consistency
    ]
    innovator_scores = [
        d.innovator_consistency for d in debates if d.innovator_consistency
    ]
    mediator_scores = [
        d.mediator_consistency for d in debates if d.mediator_consistency
    ]

    summary = {
        "proposal_id": proposal_id,
        "total_debate_sessions": total_sessions,
        "average_metrics": {
            "turns": round(avg_turns, 1),
            "duration_seconds": round(avg_duration, 1),
            "consensus_rate": round(consensus_rate, 2),
        },
        "persona_consistency": {
            "legacy_keeper_avg": (
                round(sum(legacy_scores) / len(legacy_scores), 2)
                if legacy_scores
                else None
            ),
            "innovator_avg": (
                round(sum(innovator_scores) / len(innovator_scores), 2)
                if innovator_scores
                else None
            ),
            "mediator_avg": (
                round(sum(mediator_scores) / len(mediator_scores), 2)
                if mediator_scores
                else None
            ),
        },
        "latest_debate_id": str(debates[0].id),
    }

    logger.info(
        "debate_summary_generated", proposal_id=proposal_id, sessions=total_sessions
    )
    return summary
