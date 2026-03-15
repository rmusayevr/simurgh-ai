"""
Project endpoints for project management.

Provides:
    - CRUD for projects (create, read, list, update, delete)
    - Project member management (add, remove, update roles)
    - Project document listing
    - Project proposal listing
    - Access control (owner/member/admin permissions)

All endpoints use ProjectService for business logic.
"""

import structlog
from typing import Annotated, List

from fastapi import APIRouter, Depends, status, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session, get_current_user, PaginationParams
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectRead,
    ProjectListRead,
    ProjectMemberAdd,
    ProjectMemberUpdate,
    HistoricalDocumentRead,
)
from app.schemas.proposal import ProposalListRead
from app.services.project_service import ProjectService
from app.services.proposal_service import ProposalService
from app.services.document_service import DocumentService

logger = structlog.get_logger()
router = APIRouter()


# ==================== Create ====================


@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new project.

    User becomes the project owner automatically.

    Args:
        project_in: Project data (name, description, tags, etc.)
        current_user: Authenticated user

    Returns:
        ProjectRead: Created project
    """
    log = logger.bind(operation="create_project", user_id=current_user.id)

    project_service = ProjectService(session)

    project = await project_service.create_project(
        project_data=project_in,
        owner_id=current_user.id,
    )

    log.info("project_created", project_id=project.id)
    return project


# ==================== Read ====================


@router.get("/", response_model=List[ProjectListRead])
async def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
    include_archived: bool = Query(default=False),
):
    """
    List all projects accessible to current user.

    Returns:
        - User's owned projects
        - Projects where user is a member
        - All projects if user is admin

    Args:
        include_archived: Include archived projects (default: False)

    Returns:
        List[ProjectListRead]: Accessible projects
    """
    project_service = ProjectService(session)

    projects = await project_service.get_user_projects(
        user_id=current_user.id,
        user_role=current_user.role,
        include_archived=include_archived,
    )

    return projects


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Get project details.

    Requires user to be owner, member, or admin.

    Args:
        project_id: Project ID

    Returns:
        ProjectRead: Project details

    Raises:
        NotFoundException: If project not found or user lacks access
    """
    project_service = ProjectService(session)

    project = await project_service.get_project_by_id(
        project_id=project_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    return project


# ==================== Update ====================


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int,
    project_update: ProjectUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Update project details.

    Requires owner or admin privileges.

    Args:
        project_id: Project ID
        project_update: Fields to update

    Returns:
        ProjectRead: Updated project

    Raises:
        NotFoundException: If project not found
        ForbiddenException: If user lacks permission
    """
    project_service = ProjectService(session)

    project = await project_service.update_project(
        project_id=project_id,
        data=project_update,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    logger.info("project_updated", project_id=project_id)
    return project


# ==================== Archive/Unarchive ====================


@router.post("/{project_id}/archive", response_model=ProjectRead)
async def archive_project(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Archive a project.

    Archived projects are hidden from default list views but retain all data.

    Args:
        project_id: Project ID

    Returns:
        ProjectRead: Archived project

    Raises:
        NotFoundException: If project not found
        ForbiddenException: If user lacks permission
    """
    project_service = ProjectService(session)

    project = await project_service.archive_project(
        project_id=project_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    logger.info("project_archived", project_id=project_id)
    return project


@router.post("/{project_id}/unarchive", response_model=ProjectRead)
async def unarchive_project(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Unarchive a project.

    Args:
        project_id: Project ID

    Returns:
        ProjectRead: Unarchived project

    Raises:
        NotFoundException: If project not found
        ForbiddenException: If user lacks permission
    """
    project_service = ProjectService(session)

    project = await project_service.unarchive_project(
        project_id=project_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    logger.info("project_unarchived", project_id=project_id)
    return project


# ==================== Delete ====================


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Permanently delete a project and all associated data.

    Requires owner or admin privileges.
    Cannot be undone - use archive instead for soft delete.

    Args:
        project_id: Project ID

    Returns:
        None (204 No Content)

    Raises:
        NotFoundException: If project not found
        ForbiddenException: If user lacks permission
    """
    project_service = ProjectService(session)

    await project_service.delete_project(
        project_id=project_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    logger.info("project_deleted", project_id=project_id)
    return None


# ==================== Member Management ====================


@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: int,
    member_data: ProjectMemberAdd,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Add a member to the project.

    Requires owner or admin privileges.

    Args:
        project_id: Project ID
        member_data: User email and role to assign

    Returns:
        dict: Success message with member details

    Raises:
        NotFoundException: If project or user not found
        ForbiddenException: If user lacks permission
        BadRequestException: If user already a member
    """
    log = logger.bind(operation="add_member", project_id=project_id)

    project_service = ProjectService(session)

    # Get target user by id
    from sqlmodel import select
    from app.models.user import User as UserModel

    result = await session.exec(
        select(UserModel).where(UserModel.email == member_data.email)
    )
    target_user = result.first()

    if not target_user:
        raise NotFoundException(f"User with email '{member_data.email}' not found")

    await project_service.add_member(
        project_id=project_id,
        target_user_id=target_user.id,
        role=member_data.role,
        requester_id=current_user.id,
        requester_role=current_user.role,
    )

    log.info("member_added", target_user_id=target_user.id, role=member_data.role.value)

    return {
        "message": f"{target_user.full_name} added as {member_data.role.value}",
        "user_id": target_user.id,
        "role": member_data.role.value,
    }


@router.patch("/{project_id}/members/{user_id}")
async def update_member_role(
    project_id: int,
    user_id: int,
    member_update: ProjectMemberUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Update a member's role.

    Requires owner or admin privileges.
    Cannot change owner's role.

    Args:
        project_id: Project ID
        user_id: Target user ID
        member_update: New role

    Returns:
        dict: Success message

    Raises:
        NotFoundException: If project or member not found
        ForbiddenException: If user lacks permission
        BadRequestException: If trying to change owner role
    """
    project_service = ProjectService(session)

    await project_service.update_member_role(
        project_id=project_id,
        target_user_id=user_id,
        new_role=member_update.role,
        requester_id=current_user.id,
        requester_role=current_user.role,
    )

    logger.info(
        "member_role_updated",
        project_id=project_id,
        target_user_id=user_id,
        new_role=member_update.role.value,
    )

    return {
        "message": "Member role updated successfully",
        "user_id": user_id,
        "new_role": member_update.role.value,
    }


@router.delete(
    "/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_member(
    project_id: int,
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Remove a member from the project.

    Requires owner or admin privileges.
    Cannot remove owner.

    Args:
        project_id: Project ID
        user_id: User ID to remove

    Returns:
        None (204 No Content)

    Raises:
        NotFoundException: If project or member not found
        ForbiddenException: If user lacks permission
        BadRequestException: If trying to remove owner
    """
    project_service = ProjectService(session)

    await project_service.remove_member(
        project_id=project_id,
        target_user_id=user_id,
        requester_id=current_user.id,
        requester_role=current_user.role,
    )

    logger.info("member_removed", project_id=project_id, target_user_id=user_id)
    return None


# ==================== Related Resources ====================


@router.get("/{project_id}/proposals", response_model=List[ProposalListRead])
async def list_project_proposals(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(),
):
    """
    List all proposals for a project.

    Requires project access.

    Args:
        project_id: Project ID
        pagination: Skip/limit params

    Returns:
        List[ProposalListRead]: Project proposals

    Raises:
        NotFoundException: If project not found or user lacks access
    """
    # Verify access via project service
    project_service = ProjectService(session)
    await project_service.get_project_by_id(
        project_id=project_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    # Get proposals
    proposal_service = ProposalService(session)
    proposals = await proposal_service.get_proposals_by_project(
        project_id=project_id,
        limit=pagination.limit,
    )

    return proposals


@router.get("/{project_id}/documents", response_model=List[HistoricalDocumentRead])
async def list_project_documents(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    List all historical documents for a project.

    Requires project access.

    Args:
        project_id: Project ID

    Returns:
        List[HistoricalDocumentRead]: Project documents

    Raises:
        NotFoundException: If project not found or user lacks access
    """
    document_service = DocumentService(session)

    documents = await document_service.get_project_documents(
        project_id=project_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    return documents
