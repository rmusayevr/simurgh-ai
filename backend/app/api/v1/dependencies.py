"""
FastAPI dependencies for authentication and authorization.

Provides:
    - User authentication via JWT tokens
    - Role-based access control (RBAC)
    - Project membership verification
    - Permission checking utilities

Usage:
    @router.get("/projects/{project_id}")
    async def get_project(
        project: Project = Depends(get_project_for_user),
        current_user: User = Depends(get_current_user),
    ):
        return project
"""

from typing import Annotated, Optional

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.security import decode_token
from app.core.exceptions import (
    UnauthorizedException,
    ForbiddenException,
    NotFoundException,
)
from app.db.session import get_session
from app.models.user import User, UserRole
from app.models.project import Project
from app.models.links import ProjectStakeholderLink

logger = structlog.get_logger(__name__)

# OAuth2 scheme for Swagger UI integration
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/token",
    scheme_name="JWT",
)


# ==================== Authentication Dependencies ====================


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """
    Get current authenticated user from JWT token.

    Args:
        token: JWT access token from Authorization header
        session: Database session

    Returns:
        User: Authenticated user object

    Raises:
        UnauthorizedException: If token is invalid or user not found

    Example:
        @router.get("/me")
        async def get_me(user: User = Depends(get_current_user)):
            return user
    """
    try:
        # Decode and validate token
        payload = decode_token(token, expected_type="access")
        user_id_str = payload.get("sub")

        if not user_id_str:
            logger.warning("token_missing_subject")
            raise UnauthorizedException("Invalid token: missing user ID")

        # Convert to integer
        try:
            user_id = int(user_id_str)
        except ValueError:
            logger.warning("token_invalid_user_id", user_id=user_id_str)
            raise UnauthorizedException("Invalid token: malformed user ID")

    except UnauthorizedException:
        raise
    except Exception as e:
        logger.error("token_decode_error", error=str(e))
        raise UnauthorizedException("Could not validate credentials")

    # Fetch user from database
    try:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            logger.warning("user_not_found", user_id=user_id)
            raise UnauthorizedException("User not found")

        # Check if user is active
        if not user.is_active:
            logger.warning("inactive_user_attempt", user_id=user_id)
            raise UnauthorizedException("User account is inactive")

        logger.debug("user_authenticated", user_id=user.id, email=user.email)
        return user

    except UnauthorizedException:
        raise
    except Exception as e:
        logger.error("user_fetch_error", error=str(e))
        raise UnauthorizedException("Authentication failed")


async def get_current_user_optional(
    token: Annotated[Optional[str], Depends(oauth2_scheme)] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> Optional[User]:
    """
    Get current user if authenticated, otherwise return None.

    Useful for endpoints that work for both authenticated and anonymous users.

    Args:
        token: Optional JWT token
        session: Database session

    Returns:
        User | None: User if authenticated, None otherwise

    Example:
        @router.get("/public/projects")
        async def get_projects(user: Optional[User] = Depends(get_current_user_optional)):
            if user:
                # Show user's projects
            else:
                # Show public projects only
    """
    if not token:
        return None

    try:
        return await get_current_user(token, session)
    except UnauthorizedException:
        return None


# ==================== Authorization Dependencies ====================


async def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Ensure current user has admin privileges.

    Args:
        current_user: Authenticated user

    Returns:
        User: Admin user

    Raises:
        ForbiddenException: If user is not an admin

    Example:
        @router.post("/admin/settings")
        async def update_settings(admin: User = Depends(get_current_admin)):
            # Only admins can access
    """
    if current_user.role != UserRole.ADMIN and not current_user.is_superuser:
        logger.warning(
            "admin_access_denied",
            user_id=current_user.id,
            role=current_user.role,
        )
        raise ForbiddenException(
            message="Admin privileges required",
            detail={"required_role": "ADMIN", "current_role": current_user.role.value},
        )

    logger.debug("admin_access_granted", user_id=current_user.id)
    return current_user


async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Ensure current user is a superuser.

    Superusers have unrestricted access to all resources.

    Args:
        current_user: Authenticated user

    Returns:
        User: Superuser

    Raises:
        ForbiddenException: If user is not a superuser

    Example:
        @router.delete("/admin/users/{user_id}")
        async def delete_user(superuser: User = Depends(get_current_superuser)):
            # Only superusers can delete users
    """
    if not current_user.is_superuser:
        logger.warning("superuser_access_denied", user_id=current_user.id)
        raise ForbiddenException(
            message="Superuser privileges required", detail={"is_superuser": False}
        )

    logger.debug("superuser_access_granted", user_id=current_user.id)
    return current_user


# ==================== Resource Access Dependencies ====================


async def get_project_for_user(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Project:
    """
    Get project with membership verification.

    Ensures user has access to the requested project by checking:
        - User is project owner
        - User is project stakeholder
        - User is admin/superuser

    Args:
        project_id: ID of project to fetch
        current_user: Authenticated user
        session: Database session

    Returns:
        Project: Project with preloaded relationships

    Raises:
        NotFoundException: If project doesn't exist
        ForbiddenException: If user lacks access

    Example:
        @router.get("/projects/{project_id}")
        async def get_project(project: Project = Depends(get_project_for_user)):
            return project
    """
    # Fetch project with relationships
    statement = (
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.owner),
            selectinload(Project.stakeholder_links).selectinload(
                ProjectStakeholderLink.user
            ),
            selectinload(Project.historical_documents),
        )
    )

    try:
        result = await session.execute(statement)
        project = result.scalar_one_or_none()
    except Exception as e:
        logger.error("project_fetch_error", project_id=project_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch project",
        )

    # Check if project exists
    if not project:
        logger.info("project_not_found", project_id=project_id)
        raise NotFoundException(
            message="Project not found", detail={"project_id": project_id}
        )

    # Check access permissions
    has_access = check_project_access(project, current_user)

    if not has_access:
        logger.warning(
            "project_access_denied",
            project_id=project_id,
            user_id=current_user.id,
        )
        raise ForbiddenException(
            message="Not authorized to access this project",
            detail={"project_id": project_id},
        )

    logger.debug(
        "project_access_granted",
        project_id=project_id,
        user_id=current_user.id,
    )
    return project


async def get_project_for_user_optional(
    project_id: int,
    current_user: Annotated[Optional[User], Depends(get_current_user_optional)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Optional[Project]:
    """
    Get project if user has access, otherwise return None.

    Useful for public/private hybrid endpoints.

    Args:
        project_id: Project ID
        current_user: Optional authenticated user
        session: Database session

    Returns:
        Project | None: Project if accessible, None otherwise
    """
    if not current_user:
        return None

    try:
        return await get_project_for_user(project_id, current_user, session)
    except (NotFoundException, ForbiddenException):
        return None


# ==================== Permission Checking Utilities ====================


def check_project_access(project: Project, user: User) -> bool:
    """
    Check if user has access to project.

    Args:
        project: Project to check
        user: User to verify

    Returns:
        bool: True if user has access
    """
    # Superuser has access to everything
    if user.is_superuser:
        return True

    # Admin has access to everything
    if user.role == UserRole.ADMIN:
        return True

    # Owner has access
    if project.owner_id == user.id:
        return True

    # Stakeholder has access
    is_stakeholder = any(link.user_id == user.id for link in project.stakeholder_links)
    if is_stakeholder:
        return True

    return False


def check_project_ownership(project: Project, user: User) -> bool:
    """
    Check if user is project owner (or superuser).

    Args:
        project: Project to check
        user: User to verify

    Returns:
        bool: True if user is owner
    """
    return user.is_superuser or project.owner_id == user.id


def require_project_owner(project: Project, user: User) -> None:
    """
    Raise exception if user is not project owner.

    Args:
        project: Project to check
        user: User to verify

    Raises:
        ForbiddenException: If user is not owner

    Example:
        require_project_owner(project, current_user)
        # Code only runs if user is owner
    """
    if not check_project_ownership(project, user):
        logger.warning(
            "project_owner_required",
            project_id=project.id,
            user_id=user.id,
        )
        raise ForbiddenException(
            message="Project owner privileges required",
            detail={"project_id": project.id},
        )


def require_role(user: User, required_role: UserRole) -> None:
    """
    Raise exception if user doesn't have required role.

    Args:
        user: User to check
        required_role: Required role

    Raises:
        ForbiddenException: If user lacks required role

    Example:
        require_role(current_user, UserRole.ADMIN)
    """
    if user.role != required_role and not user.is_superuser:
        logger.warning(
            "role_required",
            user_id=user.id,
            current_role=user.role,
            required_role=required_role,
        )
        raise ForbiddenException(
            message=f"Role {required_role.value} required",
            detail={
                "required_role": required_role.value,
                "current_role": user.role.value,
            },
        )


# ==================== Pagination Dependencies ====================


class PaginationParams:
    """
    Reusable pagination parameters.

    Usage:
        @router.get("/items")
        async def get_items(pagination: PaginationParams = Depends()):
            skip = pagination.skip
            limit = pagination.limit
    """

    def __init__(
        self,
        skip: int = 0,
        limit: int = 100,
    ):
        self.skip = max(0, skip)
        self.limit = min(limit, 1000)  # Max 1000 items per page
