"""
Admin - User management endpoints.

GET /admin/users
POST /admin/users
GET /admin/users/{user_id}
PATCH /admin/users/{user_id}
DELETE /admin/users/{user_id}
"""

import structlog
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session, get_current_superuser, PaginationParams
from app.core.exceptions import NotFoundException, BadRequestException
from app.models.user import User, UserRole
from app.models.project import Project
from app.models.proposal import Proposal
from app.schemas.user import (
    AdminUserResponse,
    AdminUserUpdate,
    AdminParticipantCreate,
)
from app.services.user_service import UserService

logger = structlog.get_logger()
router = APIRouter()


@router.get("/users", response_model=List[AdminUserResponse])
async def list_all_users(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(),
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
):
    """
    List all users with optional filters.
    """
    query = select(User).order_by(User.id)

    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    query = query.offset(pagination.skip).limit(pagination.limit)

    result = await session.exec(query)
    return result.all()


@router.post("/users", status_code=201)
async def create_participant(
    data: AdminParticipantCreate,
    session: AsyncSession = Depends(get_session),
):
    """
    Create a study participant account (admin only).
    """
    from app.core.security import hash_password

    existing = await session.exec(select(User).where(User.email == data.email.lower()))
    if existing.first():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=409, detail="A user with this email already exists."
        )

    user = User(
        email=data.email.lower().strip(),
        full_name=data.full_name or None,
        hashed_password=hash_password(data.password),
        is_active=True,
        is_superuser=False,
        email_verified=True,
        role=UserRole.USER,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info("participant_created", email=user.email, id=user.id)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": True,
    }


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Get detailed user information including activity stats.
    """
    user = await session.get(User, user_id)
    if not user:
        raise NotFoundException(f"User {user_id} not found")

    project_count = (
        await session.exec(
            select(func.count()).select_from(Project).where(Project.owner_id == user_id)
        )
    ).one()

    recent_proposals_stmt = (
        select(Proposal)
        .join(Project, Proposal.project_id == Project.id)
        .where(Project.owner_id == user_id)
        .order_by(Proposal.created_at.desc())
        .limit(5)
    )
    recent_proposals = (await session.exec(recent_proposals_stmt)).all()

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "created_at": user.created_at.isoformat(),
        },
        "stats": {
            "project_count": project_count,
            "proposal_count": len(recent_proposals),
        },
        "recent_activity": [
            {
                "proposal_id": p.id,
                "task_preview": p.task_description[:60] + "...",
                "status": p.status.value,
                "created_at": p.created_at.isoformat(),
            }
            for p in recent_proposals
        ],
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    data: AdminUserUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_superuser),
):
    """
    Update user as admin.
    """
    user_service = UserService(session)

    if user_id == current_user.id:
        if data.role is not None or data.is_active is not None:
            raise BadRequestException(
                "Cannot modify your own role or active status (prevents lockout)"
            )

    try:
        updated_user = await user_service.admin_update_user(
            user_id=user_id,
            data=data,
        )

        return {
            "id": updated_user.id,
            "email": updated_user.email,
            "full_name": updated_user.full_name,
            "role": updated_user.role.value,
            "is_active": updated_user.is_active,
            "is_superuser": updated_user.is_superuser,
        }

    except NotFoundException:
        raise
    except Exception as e:
        logger.error("admin_user_update_failed", user_id=user_id, error=str(e))
        raise BadRequestException(f"Failed to update user: {str(e)}")


@router.delete("/users/{user_id}", status_code=200)
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_superuser),
):
    """
    Delete a user account and all associated data.
    """
    if user_id == current_user.id:
        raise BadRequestException("Cannot delete your own account")

    user = await session.get(User, user_id)
    if not user:
        raise NotFoundException(f"User {user_id} not found")

    project_count = (
        await session.exec(
            select(func.count()).select_from(Project).where(Project.owner_id == user_id)
        )
    ).one()

    if project_count > 0:
        raise BadRequestException(
            f"User owns {project_count} project(s). Delete or transfer them first."
        )

    await session.delete(user)
    await session.commit()

    logger.warning("user_deleted", user_id=user_id, email=user.email)

    return {
        "success": True,
        "deleted_user_id": user_id,
    }
