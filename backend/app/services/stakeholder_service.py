"""
Stakeholder service for managing analysis stakeholders.

Handles:
    - CRUD for stakeholders (Mendelow's Matrix positioning)
    - Sentiment tracking and updates
    - AI-powered engagement strategy generation
    - Stakeholder-project associations
    - Power-interest quadrant calculations

Stakeholders are positioned using Mendelow's Power-Interest Matrix:
    - High Power, High Interest → Key Players (manage closely)
    - High Power, Low Interest → Keep Satisfied
    - Low Power, High Interest → Keep Informed
    - Low Power, Low Interest → Monitor

Used for:
    - Stakeholder analysis and mapping
    - Communication strategy generation
    - Political navigation in architecture decisions
"""

from app.schemas.stakeholder import StakeholderCreate
import structlog
from typing import List, Optional
from datetime import datetime, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.stakeholder import (
    Stakeholder,
    InfluenceLevel,
    InterestLevel,
    Sentiment,
)
from app.models.project import Project
from app.models.user import UserRole
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
)
from app.services.ai import ai_service

logger = structlog.get_logger()


class StakeholderService:
    """
    Service for managing analysis stakeholders.

    Stakeholders are positioned on Mendelow's Power-Interest Matrix
    and have AI-generated engagement strategies.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ==================== Create ====================

    async def create_stakeholder(
        self,
        project_id: int,
        user_id: int,
        user_role: UserRole,
        data: StakeholderCreate,
    ) -> Stakeholder:
        """
        Create a new stakeholder for a project.

        Args:
            project_id: Parent project ID
            user_id: Requesting user ID
            user_role: User's system role
            name: Stakeholder's name
            role: Job title/role
            influence: Power level (LOW, MEDIUM, HIGH)
            interest: Interest level (LOW, MEDIUM, HIGH)
            email: Optional email address
            department: Optional department
            concerns: Known concerns or objections
            motivations: What motivates this stakeholder
            sentiment: Current sentiment toward project
            approval_role: Whether they have approval authority
            notify_on_approval_needed: Send notifications when approval needed

        Returns:
            Stakeholder: Created stakeholder

        Raises:
            NotFoundException: If project not found
            ForbiddenException: If user lacks access
        """
        log = logger.bind(
            operation="create_stakeholder",
            project_id=project_id,
            stakeholder_name=data.name,
        )

        # Check project access
        await self._assert_can_manage_project(project_id, user_id, user_role)

        stakeholder = Stakeholder(project_id=project_id, **data.model_dump())

        self.session.add(stakeholder)
        await self.session.commit()
        await self.session.refresh(stakeholder)

        log.info(
            "stakeholder_created",
            stakeholder_id=stakeholder.id,
            quadrant=stakeholder.power_interest_quadrant,
        )

        return stakeholder

    # ==================== Read ====================

    async def get_by_id(
        self,
        stakeholder_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> Stakeholder:
        """
        Get a stakeholder by ID with access control.

        Raises:
            NotFoundException: If stakeholder not found or user lacks access
        """
        stakeholder = await self.session.get(Stakeholder, stakeholder_id)
        if not stakeholder:
            raise NotFoundException(f"Stakeholder {stakeholder_id} not found")

        await self._assert_can_access_project(
            stakeholder.project_id, user_id, user_role
        )

        return stakeholder

    async def get_project_stakeholders(
        self,
        project_id: int,
        user_id: int,
        user_role: UserRole,
        sentiment: Optional[Sentiment] = None,
    ) -> List[Stakeholder]:
        """
        Get all stakeholders for a project.

        Args:
            project_id: Target project ID
            user_id: Requesting user ID
            user_role: User's system role
            sentiment: Optional sentiment filter

        Returns:
            List[Stakeholder]: Project stakeholders ordered by risk level

        Raises:
            ForbiddenException: If user lacks access
        """
        await self._assert_can_access_project(project_id, user_id, user_role)

        query = select(Stakeholder).where(Stakeholder.project_id == project_id)

        if sentiment:
            query = query.where(Stakeholder.sentiment == sentiment)

        query = query.order_by(
            Stakeholder.influence.desc(),
            Stakeholder.sentiment.asc(),
        )

        result = await self.session.exec(query)
        return result.unique().all()

    # ==================== Update ====================

    async def update_stakeholder(
        self,
        stakeholder_id: int,
        user_id: int,
        user_role: UserRole,
        name: Optional[str] = None,
        role: Optional[str] = None,
        influence: Optional[InfluenceLevel] = None,
        interest: Optional[InterestLevel] = None,
        sentiment: Optional[Sentiment] = None,
        email: Optional[str] = None,
        department: Optional[str] = None,
        concerns: Optional[str] = None,
        motivations: Optional[str] = None,
        approval_role: Optional[bool] = None,
        notify_on_approval_needed: Optional[bool] = None,
    ) -> Stakeholder:
        """
        Update stakeholder details.

        Only provided fields are updated.

        Raises:
            NotFoundException: If stakeholder not found
            ForbiddenException: If user lacks permission
        """
        stakeholder = await self.get_by_id(stakeholder_id, user_id, user_role)
        await self._assert_can_manage_project(
            stakeholder.project_id, user_id, user_role
        )

        # Apply updates
        if name is not None:
            stakeholder.name = name
        if role is not None:
            stakeholder.role = role
        if influence is not None:
            stakeholder.influence = influence
        if interest is not None:
            stakeholder.interest = interest
        if sentiment is not None:
            stakeholder.sentiment = sentiment
        if email is not None:
            stakeholder.email = email
        if department is not None:
            stakeholder.department = department
        if concerns is not None:
            stakeholder.concerns = concerns
        if motivations is not None:
            stakeholder.motivations = motivations
        if approval_role is not None:
            stakeholder.approval_role = approval_role
        if notify_on_approval_needed is not None:
            stakeholder.notify_on_approval_needed = notify_on_approval_needed

        stakeholder.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.add(stakeholder)
        await self.session.commit()
        await self.session.refresh(stakeholder)

        logger.info("stakeholder_updated", stakeholder_id=stakeholder_id)
        return stakeholder

    # ==================== Delete ====================

    async def delete_stakeholder(
        self,
        stakeholder_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> None:
        """
        Delete a stakeholder.

        Args:
            stakeholder_id: Stakeholder ID to delete
            user_id: Requesting user ID
            user_role: User's system role

        Raises:
            NotFoundException: If stakeholder not found
            ForbiddenException: If user lacks permission
        """
        stakeholder = await self.get_by_id(stakeholder_id, user_id, user_role)
        await self._assert_can_manage_project(
            stakeholder.project_id, user_id, user_role
        )

        await self.session.delete(stakeholder)
        await self.session.commit()

        logger.info("stakeholder_deleted", stakeholder_id=stakeholder_id)

    # ==================== AI Strategy Generation ====================

    async def generate_engagement_strategy(
        self,
        stakeholder_id: int,
        user_id: int,
        user_role: UserRole,
        extra_context: str = "",
        force_regenerate: bool = False,
    ) -> str:
        """
        Generate AI-powered engagement strategy for a stakeholder.

        Uses Claude to analyze stakeholder position (Mendelow's Matrix)
        and generate a tailored communication strategy.

        Args:
            stakeholder_id: Target stakeholder ID
            user_id: Requesting user ID
            user_role: User's system role
            extra_context: Additional context for strategy generation
            force_regenerate: Regenerate even if cached strategy exists

        Returns:
            str: Generated engagement strategy (markdown)

        Raises:
            NotFoundException: If stakeholder not found
            ForbiddenException: If user lacks access
        """
        log = logger.bind(
            operation="generate_strategy",
            stakeholder_id=stakeholder_id,
        )

        stakeholder = await self.get_by_id(stakeholder_id, user_id, user_role)

        # Check cache unless force regenerate
        if not force_regenerate and stakeholder.strategic_plan:
            log.info("strategy_cache_hit")
            return stakeholder.strategic_plan

        # Fetch project for context
        project = await self.session.get(Project, stakeholder.project_id)
        if not project:
            raise NotFoundException("Project not found")

        # Build prompt
        prompt = ai_service.build_strategy_prompt(
            stakeholder=stakeholder,
            project=project,
            extra_context=extra_context,
        )

        log.info("generating_strategy", quadrant=stakeholder.power_interest_quadrant)

        # Generate strategy
        strategy = await ai_service.generate_strategy(
            prompt=prompt,
            use_extended_thinking=False,
        )

        # Cache strategy
        stakeholder.strategic_plan = strategy
        stakeholder.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.add(stakeholder)
        await self.session.commit()

        log.info("strategy_generated_and_cached", length=len(strategy))
        return strategy

    # ==================== Analytics ====================

    async def get_stakeholder_matrix(
        self,
        project_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> dict:
        """
        Get stakeholder matrix data for visualization.

        Returns stakeholders grouped by power-interest quadrant.

        Args:
            project_id: Target project ID
            user_id: Requesting user ID
            user_role: User's system role

        Returns:
            dict: Stakeholders grouped by quadrant

        Raises:
            ForbiddenException: If user lacks access
        """
        stakeholders = await self.get_project_stakeholders(
            project_id=project_id,
            user_id=user_id,
            user_role=user_role,
        )

        # Group by quadrant
        matrix = {
            "key_players": [],  # High power, high interest
            "keep_satisfied": [],  # High power, low interest
            "keep_informed": [],  # Low power, high interest
            "monitor": [],  # Low power, low interest
        }

        for s in stakeholders:
            quadrant_map = {
                "Manage Closely": "key_players",
                "Keep Satisfied": "keep_satisfied",
                "Keep Informed": "keep_informed",
                "Monitor": "monitor",
            }
            quadrant_key = quadrant_map.get(s.power_interest_quadrant, "monitor")
            matrix[quadrant_key].append(
                {
                    "id": s.id,
                    "name": s.name,
                    "role": s.role,
                    "sentiment": s.sentiment.value,
                    "needs_attention": s.needs_attention,
                }
            )

        logger.info(
            "stakeholder_matrix_generated",
            project_id=project_id,
            total=len(stakeholders),
            key_players=len(matrix["key_players"]),
        )

        return matrix

    # ==================== Access Control ====================

    async def _assert_can_access_project(
        self,
        project_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> None:
        """
        Assert user has read access to project.

        Raises:
            ForbiddenException: If user lacks access
        """
        from app.services.project_service import ProjectService

        project_service = ProjectService(self.session)
        try:
            await project_service.get_project_by_id(
                project_id=project_id,
                user_id=user_id,
                user_role=user_role,
            )
        except NotFoundException:
            raise ForbiddenException(
                "You do not have access to this project or it does not exist"
            )

    async def _assert_can_manage_project(
        self,
        project_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> None:
        """
        Assert user has management permissions on project.

        Raises:
            ForbiddenException: If user lacks permission
        """
        from app.services.project_service import ProjectService

        project_service = ProjectService(self.session)
        await project_service.assert_can_manage(project_id, user_id, user_role)
