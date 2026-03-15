"""
Project service for project management and membership.

Handles all business logic related to projects:
    - CRUD (create, read, update, delete)
    - Archive / restore
    - Member management (add, remove, update role)
    - Access control checks (owner, admin, role-based)

All database operations are async using SQLModel + AsyncSession.
"""

import structlog
from sqlalchemy import select as sa_select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import aliased
from sqlmodel import select, or_
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List, Optional

from app.core.exceptions import (
    NotFoundException,
    ConflictException,
    ForbiddenException,
    BadRequestException,
)

from app.models.project import Project
from app.models.links import ProjectStakeholderLink, ProjectRole
from app.models.user import UserRole
from app.schemas.project import ProjectCreate, ProjectUpdate

logger = structlog.get_logger(__name__)


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ==================== Helpers ====================

    async def get_by_id_or_404(self, project_id: int) -> Project:
        """
        Fetch a project by primary key without access control.
        Used internally — access control applied in public-facing methods.

        Raises:
            HTTPException 404: If project not found
        """
        project = await self.session.get(Project, project_id)
        if not project:
            raise NotFoundException("Project not found")
        return project

    async def get_user_role(
        self,
        project_id: int,
        user_id: int,
    ) -> Optional[ProjectRole]:
        """
        Get a user's role in a project.

        Returns:
            ProjectRole | None: User's role, or None if not a member
        """
        result = await self.session.exec(
            select(ProjectStakeholderLink).where(
                ProjectStakeholderLink.project_id == project_id,
                ProjectStakeholderLink.user_id == user_id,
            )
        )
        link = result.first()
        return link.role if link else None

    async def assert_can_edit(
        self,
        project_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> None:
        """
        Assert user has edit permissions on a project.

        System ADMINs always pass.
        Project owners (matched via owner_id) always pass — this covers seeded
        projects that may not have a ProjectStakeholderLink row yet.
        Otherwise the user must have an EDITOR, ADMIN, or OWNER project role.

        Raises:
            HTTPException 403: If user lacks edit permissions
        """
        # System-level admin bypasses all checks
        if user_role == UserRole.ADMIN:
            return

        # Project owner always has full permissions regardless of link table
        project = await self.get_by_id_or_404(project_id)
        if project.owner_id == user_id:
            return

        role = await self.get_user_role(project_id, user_id)
        if not role or not role.can_edit:
            raise ForbiddenException("You do not have permission to edit this project")

    async def assert_can_manage(
        self,
        project_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> None:
        """
        Assert user has management permissions (owner or admin).

        System ADMINs always pass.
        Project owners (matched via owner_id) always pass — this covers seeded
        projects that may not have a ProjectStakeholderLink row yet.
        Otherwise the user must have an OWNER or ADMIN project role in the link table.

        Raises:
            HTTPException 403: If user lacks management permissions
        """
        # System-level admin bypasses all checks
        if user_role == UserRole.ADMIN:
            return

        # Project owner always has full management rights regardless of link table
        project = await self.get_by_id_or_404(project_id)
        if project.owner_id == user_id:
            return

        role = await self.get_user_role(project_id, user_id)
        if not role or not role.can_manage:
            raise ForbiddenException(
                "You do not have permission to manage this project"
            )

    # ==================== Read ====================

    async def get_user_projects(
        self,
        user_id: int,
        user_role: UserRole,
        include_archived: bool = False,
    ) -> List[Project]:
        """
        Get all projects visible to a user.

        Admins see all projects. Regular users see projects
        they own or are a member of. Archived projects hidden
        by default unless include_archived=True.

        Args:
            user_id: Requesting user's ID
            user_role: Requesting user's system role
            include_archived: Whether to include archived projects

        Returns:
            List[Project]: Visible projects ordered by last activity
        """
        if user_role == UserRole.ADMIN:
            statement = select(Project)
        else:
            statement = (
                select(Project)
                .join(ProjectStakeholderLink, isouter=True)
                .where(
                    or_(
                        Project.owner_id == user_id,
                        ProjectStakeholderLink.user_id == user_id,
                    )
                )
            )

        if not include_archived:
            statement = statement.where(Project.is_archived == False)  # noqa: E712

        statement = (
            statement.options(
                selectinload(Project.owner),
                selectinload(Project.stakeholder_links).selectinload(
                    ProjectStakeholderLink.user
                ),
                selectinload(Project.historical_documents),
                selectinload(Project.analysis_stakeholders),
            )
            .order_by(Project.last_activity_at.desc())
            .distinct()
        )

        result = await self.session.exec(statement)
        return result.all()

    async def get_project_by_id(
        self,
        project_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> Project:
        """
        Get a single project by ID with access control.

        Updates the requesting member's last_active_at timestamp.

        Raises:
            HTTPException 404: If project not found or not accessible
        """
        stmt = (
            sa_select(Project)
            .where(Project.id == project_id)
            .options(
                selectinload(Project.owner),
                selectinload(Project.analysis_stakeholders),
                selectinload(Project.stakeholder_links).selectinload(
                    ProjectStakeholderLink.user
                ),
                selectinload(Project.historical_documents),
            )
        )

        if user_role != UserRole.ADMIN:
            psl = aliased(ProjectStakeholderLink)
            stmt = stmt.outerjoin(psl, Project.id == psl.project_id).where(
                or_(
                    Project.owner_id == user_id,
                    psl.user_id == user_id,
                )
            )

        result = await self.session.exec(stmt)
        project = result.unique().scalar_one_or_none()

        if not project:
            raise NotFoundException("Project not found or you do not have access")

        # Update member's last active timestamp
        await self._update_member_last_active(project_id, user_id)

        return project

    # ==================== Create ====================

    async def create_project(
        self,
        project_data: ProjectCreate,
        owner_id: int,
    ) -> Project:
        """
        Create a new project and assign the creator as OWNER.

        Initializes cached counters and creates the owner's
        ProjectStakeholderLink record.

        Args:
            project_data: Project creation data
            owner_id: ID of the creating user

        Returns:
            Project: Fully loaded created project
        """
        project = Project(
            name=project_data.name,
            description=project_data.description,
            visibility=project_data.visibility,
            tags=project_data.tags,
            tech_stack=project_data.tech_stack,
            owner_id=owner_id,
            document_count=0,
            proposal_count=0,
            member_count=1,  # owner counts as first member
        )
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)

        # Create owner membership link
        owner_link = ProjectStakeholderLink(
            project_id=project.id,
            user_id=owner_id,
            role=ProjectRole.OWNER,
        )
        self.session.add(owner_link)
        await self.session.commit()

        logger.info("project_created", project_id=project.id, owner_id=owner_id)

        # Return fully loaded project
        return await self._load_full_project(project.id)

    # ==================== Update ====================

    async def update_project(
        self,
        project_id: int,
        data: ProjectUpdate,
        user_id: int,
        user_role: UserRole,
    ) -> Project:
        """
        Update project fields.

        Only OWNER, ADMIN (project role), or system ADMIN can update.

        Raises:
            HTTPException 403: If user lacks edit permissions
            HTTPException 404: If project not found
        """
        await self.assert_can_edit(project_id, user_id, user_role)
        project = await self.get_by_id_or_404(project_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)

        project.update_activity()  # updates last_activity_at + updated_at
        self.session.add(project)
        await self.session.commit()

        logger.info(
            "project_updated",
            project_id=project_id,
            fields=list(update_data.keys()),
        )

        return await self._load_full_project(project_id)

    # ==================== Archive ====================

    async def archive_project(
        self,
        project_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> Project:
        """
        Soft-delete a project (archive).

        Only OWNER or system ADMIN can archive.

        Raises:
            HTTPException 403: If user is not owner or admin
            HTTPException 400: If project already archived
        """
        await self.assert_can_manage(project_id, user_id, user_role)
        project = await self.get_by_id_or_404(project_id)

        if project.is_archived:
            raise BadRequestException("Project is already archived")

        project.archive()  # sets is_archived=True, archived_at=now
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)

        logger.info("project_archived", project_id=project_id)
        return project

    async def unarchive_project(
        self,
        project_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> Project:
        """
        Restore an archived project.

        Raises:
            HTTPException 403: If user is not owner or admin
            HTTPException 400: If project is not archived
        """
        await self.assert_can_manage(project_id, user_id, user_role)
        project = await self.get_by_id_or_404(project_id)

        if not project.is_archived:
            raise BadRequestException("Project is not archived")

        project.unarchive()  # sets is_archived=False, archived_at=None
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)

        logger.info("project_unarchived", project_id=project_id)
        return project

    # ==================== Delete ====================

    async def delete_project(
        self,
        project_id: int,
        user_id: int,
        user_role: UserRole,
    ) -> None:
        """
        Permanently delete a project and all related data.

        Cascade deletes handle: documents, chunks, proposals,
        debate sessions, stakeholder links.

        Only OWNER or system ADMIN can delete.

        Raises:
            HTTPException 403: If user is not owner or admin
        """
        project = await self.get_by_id_or_404(project_id)

        if user_role != UserRole.ADMIN and project.owner_id != user_id:
            raise ForbiddenException("Only the project owner can delete this project")

        await self.session.delete(project)
        await self.session.commit()

        logger.info("project_deleted", project_id=project_id, deleted_by=user_id)

    # ==================== Member Management ====================

    async def add_member(
        self,
        project_id: int,
        target_user_id: int,
        role: ProjectRole,
        requester_id: int,
        requester_role: UserRole,
    ) -> ProjectStakeholderLink:
        """
        Add a user to a project with a specific role.

        Checks for duplicate membership and updates cached member_count.

        Raises:
            HTTPException 403: If requester lacks manage permissions
            HTTPException 409: If user is already a member
        """
        await self.assert_can_manage(project_id, requester_id, requester_role)

        # Check for duplicate membership
        existing = await self.get_user_role(project_id, target_user_id)
        if existing is not None:
            raise ConflictException("User is already a member of this project")

        link = ProjectStakeholderLink(
            project_id=project_id,
            user_id=target_user_id,
            role=role,
            added_by_id=requester_id,
        )
        self.session.add(link)

        # Update cached member count
        project = await self.get_by_id_or_404(project_id)
        project.member_count += 1
        project.update_activity()
        self.session.add(project)

        await self.session.commit()
        await self.session.refresh(link)

        logger.info(
            "member_added",
            project_id=project_id,
            user_id=target_user_id,
            role=role.value,
        )
        return link

    async def remove_member(
        self,
        project_id: int,
        target_user_id: int,
        requester_id: int,
        requester_role: UserRole,
    ) -> None:
        """
        Remove a user from a project.

        Users can remove themselves. Managers can remove editors/viewers.
        Owner cannot be removed.

        Raises:
            HTTPException 403: If requester lacks permission
            HTTPException 400: If trying to remove the project owner
            HTTPException 404: If user is not a member
        """
        await self.assert_can_manage(project_id, requester_id, requester_role)

        result = await self.session.exec(
            select(ProjectStakeholderLink).where(
                ProjectStakeholderLink.project_id == project_id,
                ProjectStakeholderLink.user_id == target_user_id,
            )
        )
        link = result.first()

        if not link:
            raise NotFoundException("User is not a member of this project")

        if link.role == ProjectRole.OWNER:
            raise BadRequestException(
                "Project owner cannot be removed. Transfer ownership first"
            )

        await self.session.delete(link)

        # Update cached member count
        project = await self.get_by_id_or_404(project_id)
        project.member_count = max(0, project.member_count - 1)
        project.update_activity()
        self.session.add(project)

        await self.session.commit()

        logger.info(
            "member_removed",
            project_id=project_id,
            user_id=target_user_id,
        )

    async def update_member_role(
        self,
        project_id: int,
        target_user_id: int,
        new_role: ProjectRole,
        requester_id: int,
        requester_role: UserRole,
    ) -> ProjectStakeholderLink:
        """
        Update a member's role in a project.

        Cannot change the OWNER role — use transfer_ownership instead.

        Raises:
            HTTPException 403: If requester lacks manage permissions
            HTTPException 400: If trying to change owner's role
            HTTPException 404: If user is not a member
        """
        await self.assert_can_manage(project_id, requester_id, requester_role)

        result = await self.session.exec(
            select(ProjectStakeholderLink).where(
                ProjectStakeholderLink.project_id == project_id,
                ProjectStakeholderLink.user_id == target_user_id,
            )
        )
        link = result.first()

        if not link:
            raise NotFoundException("User is not a member of this project")

        if link.role == ProjectRole.OWNER:
            raise BadRequestException(
                "Cannot change the owner's role. Use transfer ownership instead"
            )

        link.role = new_role
        self.session.add(link)
        await self.session.commit()
        await self.session.refresh(link)

        logger.info(
            "member_role_updated",
            project_id=project_id,
            user_id=target_user_id,
            new_role=new_role.value,
        )
        return link

    # ==================== Private Helpers ====================

    async def _load_full_project(self, project_id: int) -> Project:
        """
        Load a project with all relationships eager-loaded.
        Used after create/update to return a fully populated object.
        """
        result = await self.session.exec(
            select(Project)
            .where(Project.id == project_id)
            .options(
                selectinload(Project.owner),
                selectinload(Project.stakeholder_links).selectinload(
                    ProjectStakeholderLink.user
                ),
                selectinload(Project.historical_documents),
                selectinload(Project.analysis_stakeholders),
            )
        )
        project = result.first()
        if not project:
            raise NotFoundException("Project not found")
        return project

    async def _update_member_last_active(
        self,
        project_id: int,
        user_id: int,
    ) -> None:
        """
        Update a member's last_active_at timestamp silently.
        Called on project detail fetch — failure should not block the response.
        """
        try:
            result = await self.session.exec(
                select(ProjectStakeholderLink).where(
                    ProjectStakeholderLink.project_id == project_id,
                    ProjectStakeholderLink.user_id == user_id,
                )
            )
            link = result.first()
            if link:
                link.update_last_active()
                self.session.add(link)
                await self.session.commit()
        except Exception:
            logger.warning(
                "member_last_active_update_failed",
                project_id=project_id,
                user_id=user_id,
            )
