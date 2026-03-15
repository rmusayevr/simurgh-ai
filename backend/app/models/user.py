"""
User model and related enums.

Represents system users with authentication, authorization, and profile data.

Relationships:
    - owned_projects: Projects created by this user
    - collaborated_projects: Projects where user is a stakeholder
    - refresh_tokens: Active refresh tokens for this user
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Index

from app.models.links import ProjectStakeholderLink

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.token import RefreshToken


# ==================== Enums ====================


class UserRole(str, Enum):
    """
    User role for role-based access control (RBAC).

    Roles (in order of privilege):
        ADMIN: Full system access, can manage all projects and users
        MANAGER: Can create and manage own projects
        USER: Can only view and edit assigned projects
    """

    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    USER = "USER"

    @classmethod
    def default(cls) -> "UserRole":
        """Get default role for new users."""
        return cls.USER

    @property
    def display_name(self) -> str:
        """Get human-readable role name."""
        return self.value.title()


# ==================== User Model ====================


class User(SQLModel, table=True):
    """
    User account model.

    Stores authentication credentials, profile information, and authorization data.
    Supports email verification, password reset, and multi-device sessions.

    Attributes:
        id: Primary key
        email: Unique email address (used for login)
        hashed_password: Bcrypt-hashed password
        full_name: User's display name
        job_title: Professional title (e.g., "Senior Architect")
        avatar_url: URL to user's profile picture
        role: User role for RBAC
        is_active: Account activation status
        is_superuser: Superuser flag (bypass all permissions)
        email_verified: Email verification status
        terms_accepted: Terms of service acceptance
        last_login: Last successful login timestamp
        reset_token: Temporary password reset token
        reset_token_expires_at: Reset token expiration
        verification_token: Email verification token
        created_at: Account creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "users"

    # ==================== Primary Key ====================

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="User ID",
    )

    # ==================== Authentication ====================

    email: str = Field(
        unique=True,
        index=True,
        nullable=False,
        max_length=255,
        description="User email address (unique, used for login)",
    )

    hashed_password: str = Field(
        nullable=False,
        description="Bcrypt-hashed password",
    )

    # ==================== Profile ====================

    full_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="User's full name",
    )

    job_title: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Professional title (e.g., 'Senior Software Architect')",
    )

    avatar_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL to user's profile picture",
    )

    # ==================== Authorization ====================

    role: UserRole = Field(
        default=UserRole.USER,
        description="User role for RBAC",
    )

    is_active: bool = Field(
        default=False,
        description="Account activation status (False until email verified)",
    )

    is_superuser: bool = Field(
        default=False,
        description="Superuser flag (bypasses all permission checks)",
    )

    # ==================== Email Verification ====================

    email_verified: bool = Field(
        default=False,
        description="Email verification status",
    )

    verification_token: Optional[str] = Field(
        default=None,
        index=True,
        max_length=255,
        description="Email verification token (null after verification)",
    )

    # ==================== Legal & Compliance ====================

    terms_accepted: bool = Field(
        default=False,
        description="Terms of service acceptance status",
    )

    terms_accepted_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of terms acceptance",
    )

    # ==================== OAuth ====================

    github_id: Optional[str] = Field(
        default=None,
        max_length=50,
        unique=True,
        index=True,
        description="GitHub user ID for OAuth login",
    )

    github_username: Optional[str] = Field(
        default=None,
        max_length=100,
        description="GitHub username (for display)",
    )

    oauth_provider: Optional[str] = Field(
        default=None,
        max_length=20,
        description="OAuth provider used to create/link this account: 'github' | 'google' | 'atlassian'",
    )

    # ==================== Password Reset ====================

    reset_token: Optional[str] = Field(
        default=None,
        index=True,
        max_length=255,
        description="Password reset token (temporary)",
    )

    reset_token_expires_at: Optional[datetime] = Field(
        default=None,
        description="Password reset token expiration timestamp",
    )

    # ==================== Activity Tracking ====================

    last_login: Optional[datetime] = Field(
        default=None,
        description="Last successful login timestamp",
    )

    login_count: int = Field(
        default=0,
        description="Total number of successful logins",
    )

    # ==================== Timestamps ====================

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        description="Account creation timestamp (UTC)",
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc).replace(tzinfo=None)
        },
        description="Last update timestamp (UTC)",
    )

    # ==================== Relationships ====================

    owned_projects: List["Project"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
        },
    )

    # collaborated_projects: List["Project"] = Relationship(
    #     back_populates="members",
    #     link_model=ProjectStakeholderLink,
    #     sa_relationship_kwargs={
    #         "lazy": "selectin",
    #         "overlaps": "stakeholder_links",
    #     },
    # )

    stakeholder_links: List["ProjectStakeholderLink"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
            "foreign_keys": "[ProjectStakeholderLink.user_id]",
        },
    )

    refresh_tokens: List["RefreshToken"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
        },
    )

    # ==================== Indexes ====================

    __table_args__ = (
        Index("idx_user_email_verified", "email", "email_verified"),
        Index("idx_user_role_active", "role", "is_active"),
        Index("idx_user_created_at", "created_at"),
    )

    # ==================== Helper Methods ====================

    @property
    def collaborated_projects(self) -> List["Project"]:
        return [link.project for link in self.stakeholder_links]

    @property
    def is_verified(self) -> bool:
        """Check if user has verified their email."""
        return self.email_verified

    @property
    def can_login(self) -> bool:
        """Check if user can log in (active and verified)."""
        return self.is_active and self.email_verified

    @property
    def display_name(self) -> str:
        """Get user's display name (full name or email)."""
        return self.full_name or self.email.split("@")[0]

    def has_role(self, role: UserRole) -> bool:
        """
        Check if user has specified role or higher.

        Args:
            role: Role to check

        Returns:
            bool: True if user has role or is superuser
        """
        if self.is_superuser:
            return True

        role_hierarchy = {
            UserRole.USER: 1,
            UserRole.MANAGER: 2,
            UserRole.ADMIN: 3,
        }

        return role_hierarchy.get(self.role, 0) >= role_hierarchy.get(role, 0)

    def update_last_login(self) -> None:
        """Update last login timestamp and increment login count."""
        self.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
        self.login_count += 1

    def clear_reset_token(self) -> None:
        """Clear password reset token."""
        self.reset_token = None
        self.reset_token_expires_at = None

    def clear_verification_token(self) -> None:
        """Clear email verification token."""
        self.verification_token = None

    def verify_email(self) -> None:
        """Mark email as verified and activate account."""
        self.email_verified = True
        self.is_active = True
        self.clear_verification_token()

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<User(id={self.id}, email={self.email}, role={self.role.value})>"

    def __str__(self) -> str:
        """Human-readable string representation."""
        return self.display_name


# ==================== Update Schema ====================


class RoleUpdate(SQLModel):
    """Schema for updating user role (admin only)."""

    role: UserRole = Field(
        description="New role to assign to user",
    )
