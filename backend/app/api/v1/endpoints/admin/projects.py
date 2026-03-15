"""
Admin - Project management endpoints.

GET /admin/projects
DELETE /admin/projects/{project_id}
"""

import structlog

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session, get_current_superuser, PaginationParams
from app.models.user import User
from app.models.project import Project
from app.schemas.user import AdminProjectResponse
from app.services.project_service import ProjectService

logger = structlog.get_logger()
router = APIRouter()


@router.get("/projects", response_model=list[AdminProjectResponse])
async def list_all_projects(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(),
):
    """
    List all projects with owner info and proposal counts.
    """
    stmt = (
        select(Project, User.email)
        .join(User, Project.owner_id == User.id)
        .order_by(Project.created_at.desc())
        .offset(pagination.skip)
        .limit(pagination.limit)
    )

    results = (await session.exec(stmt)).unique().all()

    return [
        AdminProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            owner_email=email,
            created_at=project.created_at,
            proposal_count=project.proposal_count,
            document_count=project.document_count,
            member_count=project.member_count,
        )
        for project, email in results
    ]


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_superuser),
):
    """
    Delete a project and all associated data (cascade).
    """
    project_service = ProjectService(session)

    await project_service.delete_project(
        project_id=project_id,
        user_id=current_user.id,
        user_role=current_user.role,
    )

    return {
        "success": True,
        "message": "Project and all associated data deleted",
    }
