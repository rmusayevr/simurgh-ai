"""
Stakeholder endpoints for stakeholder management and AI strategy generation.

Provides:
    - CRUD for stakeholders (create, read, update, delete)
    - AI-powered engagement strategy generation
    - Stakeholder matrix visualization (Mendelow's Power-Interest Matrix)
    - Bulk strategy generation
    - Sentiment tracking

Stakeholder Analysis:
    - Mendelow's Matrix: Power (influence) vs Interest grid
    - Quadrants: Key Players, Keep Satisfied, Keep Informed, Monitor
    - AI strategies tailored to stakeholder position and sentiment
"""

import structlog
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session, get_current_user
from app.core.exceptions import NotFoundException, BadRequestException
from app.models.user import User
from app.models.stakeholder import Sentiment
from app.schemas.stakeholder import (
    StakeholderCreate,
    StakeholderRead,
    StakeholderUpdate,
    StakeholderMatrix,
)
from app.services.stakeholder_service import StakeholderService

logger = structlog.get_logger()
router = APIRouter()


# ==================== CRUD ====================


@router.post("/project/{project_id}", response_model=StakeholderRead, status_code=201)
async def create_stakeholder(
    project_id: int,
    stakeholder_data: StakeholderCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new stakeholder for a project.

    Args:
        project_id: Target project ID
        stakeholder_data: Stakeholder details

    Returns:
        StakeholderRead: Created stakeholder

    Raises:
        ForbiddenException: If user lacks project access
        BadRequestException: If validation fails
    """
    log = logger.bind(operation="create_stakeholder", project_id=project_id)

    stakeholder_service = StakeholderService(session)

    stakeholder = await stakeholder_service.create_stakeholder(
        project_id=project_id,
        user_id=current_user.id,
        user_role=current_user.role,
        data=stakeholder_data,
    )

    log.info("stakeholder_created", stakeholder_id=stakeholder.id)
    return stakeholder


@router.get("/project/{project_id}", response_model=List[StakeholderRead])
async def list_stakeholders(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
    sentiment: Optional[Sentiment] = Query(default=None),
):
    """
    List all stakeholders for a project.

    Args:
        project_id: Project ID
        sentiment: Optional sentiment filter

    Returns:
        List[StakeholderRead]: Project stakeholders ordered by risk level

    Raises:
        ForbiddenException: If user lacks project access
    """
    stakeholder_service = StakeholderService(session)

    stakeholders = await stakeholder_service.get_project_stakeholders(
        project_id=project_id,
        user_id=current_user.id,
        user_role=current_user.role,
        sentiment=sentiment,
    )

    return stakeholders


@router.get("/{stakeholder_id}", response_model=StakeholderRead)
async def get_stakeholder(
    stakeholder_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Get a specific stakeholder by ID.

    Args:
        stakeholder_id: Stakeholder ID

    Returns:
        StakeholderRead: Stakeholder details

    Raises:
        NotFoundException: If stakeholder not found or user lacks access
    """
    stakeholder_service = StakeholderService(session)

    stakeholder = await stakeholder_service.get_by_id(
        stakeholder_id=stakeholder_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    return stakeholder


@router.patch("/{stakeholder_id}", response_model=StakeholderRead)
async def update_stakeholder(
    stakeholder_id: int,
    stakeholder_update: StakeholderUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Update a stakeholder.

    Args:
        stakeholder_id: Stakeholder ID
        stakeholder_update: Fields to update

    Returns:
        StakeholderRead: Updated stakeholder

    Raises:
        NotFoundException: If stakeholder not found
        ForbiddenException: If user lacks permission
    """
    log = logger.bind(operation="update_stakeholder", stakeholder_id=stakeholder_id)

    stakeholder_service = StakeholderService(session)

    stakeholder = await stakeholder_service.update_stakeholder(
        stakeholder_id=stakeholder_id,
        user_id=current_user.id,
        user_role=current_user.role,
        **stakeholder_update.model_dump(exclude_unset=True),
    )

    log.info("stakeholder_updated")
    return stakeholder


@router.delete("/{stakeholder_id}", status_code=204)
async def delete_stakeholder(
    stakeholder_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Delete a stakeholder.

    Args:
        stakeholder_id: Stakeholder ID to delete

    Returns:
        None (204 No Content)

    Raises:
        NotFoundException: If stakeholder not found
        ForbiddenException: If user lacks permission
    """
    stakeholder_service = StakeholderService(session)

    await stakeholder_service.delete_stakeholder(
        stakeholder_id=stakeholder_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    logger.info("stakeholder_deleted", stakeholder_id=stakeholder_id)
    return None


# ==================== AI Strategy Generation ====================


@router.post("/{stakeholder_id}/strategy")
async def generate_engagement_strategy(
    stakeholder_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
    force_regenerate: bool = Query(default=False),
    extra_context: str = Query(default="", max_length=1000),
):
    """
    Generate AI-powered engagement strategy.

    Analyzes stakeholder position (Mendelow's Matrix) and generates:
    - Psychological profile
    - Strategic approach
    - Key talking points
    - Sample outreach message
    - Anticipated objections

    Args:
        stakeholder_id: Stakeholder ID
        force_regenerate: Regenerate even if cached
        extra_context: Additional context for strategy generation

    Returns:
        dict: Strategy markdown and metadata

    Raises:
        NotFoundException: If stakeholder not found
        ForbiddenException: If user lacks access
    """
    log = logger.bind(operation="generate_strategy", stakeholder_id=stakeholder_id)

    stakeholder_service = StakeholderService(session)

    try:
        strategy = await stakeholder_service.generate_engagement_strategy(
            stakeholder_id=stakeholder_id,
            user_id=current_user.id,
            user_role=current_user.role,
            extra_context=extra_context,
            force_regenerate=force_regenerate,
        )

        log.info("strategy_generated", cached=not force_regenerate)

        return {
            "strategy": strategy,
            "cached": not force_regenerate,
        }

    except (NotFoundException, BadRequestException):
        raise
    except Exception as e:
        log.error("strategy_generation_failed", error=str(e))
        raise BadRequestException(f"Strategy generation failed: {str(e)}")


@router.delete("/{stakeholder_id}/strategy")
async def delete_strategy(
    stakeholder_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Delete cached engagement strategy.

    Forces regeneration on next request.

    Args:
        stakeholder_id: Stakeholder ID

    Returns:
        dict: Success message

    Raises:
        NotFoundException: If stakeholder not found or no strategy exists
    """
    stakeholder_service = StakeholderService(session)

    stakeholder = await stakeholder_service.get_by_id(
        stakeholder_id=stakeholder_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    if not stakeholder.strategic_plan:
        raise NotFoundException("No strategy exists for this stakeholder")

    from app.models.stakeholder import Stakeholder

    # Clear strategy
    db_stakeholder = await session.get(Stakeholder, stakeholder_id)
    db_stakeholder.strategic_plan = None
    session.add(db_stakeholder)
    await session.commit()

    logger.info("strategy_deleted", stakeholder_id=stakeholder_id)

    return {
        "success": True,
        "message": "Strategy deleted. Next request will regenerate.",
    }


# ==================== Analytics & Visualization ====================


@router.get("/project/{project_id}/matrix", response_model=StakeholderMatrix)
async def get_stakeholder_matrix(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Get stakeholder matrix for visualization.

    Groups stakeholders by Mendelow's Power-Interest quadrants:
    - Key Players (high power, high interest)
    - Keep Satisfied (high power, low interest)
    - Keep Informed (low power, high interest)
    - Monitor (low power, low interest)

    Args:
        project_id: Project ID

    Returns:
        StakeholderMatrix: Stakeholders grouped by quadrant

    Raises:
        ForbiddenException: If user lacks project access
    """
    stakeholder_service = StakeholderService(session)

    matrix = await stakeholder_service.get_stakeholder_matrix(
        project_id=project_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    return matrix
