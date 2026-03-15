"""
Stakeholder and ProjectStakeholderLink models.

Stakeholder represents AI-analyzed personas within a project context,
mapping real-world roles and their influence on architectural decisions.

ProjectStakeholderLink is the many-to-many association between Users
and Projects with role-based permissions.

Models:
    - Stakeholder: AI-defined stakeholder persona for a project
    - ProjectStakeholderLink: User-Project membership with role

Relationships:
    Stakeholder -> Project (many stakeholders per project)
    ProjectStakeholderLink -> Project, User (junction table)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Index

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


# ==================== Project Role Enum ====================


class ProjectRole(str, Enum):
    """
    User's role within a project.

    Roles (in order of privilege):
        OWNER: Full control, can delete project and manage all members
        ADMIN: Can manage members, proposals, and settings
        EDITOR: Can create/edit proposals and upload documents
        VIEWER: Read-only access to project content
    """

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"

    @property
    def can_edit(self) -> bool:
        """Check if role has edit permissions."""
        return self in (ProjectRole.OWNER, ProjectRole.ADMIN, ProjectRole.EDITOR)

    @property
    def can_manage(self) -> bool:
        """Check if role can manage project settings and members."""
        return self in (ProjectRole.OWNER, ProjectRole.ADMIN)

    @property
    def can_delete(self) -> bool:
        """Check if role can delete the project."""
        return self == ProjectRole.OWNER

    @property
    def privilege_level(self) -> int:
        """Numeric privilege level for comparisons."""
        return {
            ProjectRole.VIEWER: 1,
            ProjectRole.EDITOR: 2,
            ProjectRole.ADMIN: 3,
            ProjectRole.OWNER: 4,
        }[self]


# ==================== ProjectStakeholderLink Model ====================


class ProjectStakeholderLink(SQLModel, table=True):
    """
    Many-to-many association between Users and Projects.

    Stores user's role within a project and metadata
    about when they joined and who added them.

    Attributes:
        project_id: FK to project (composite PK)
        user_id: FK to user (composite PK)
        role: User's role in this project
        added_by_id: Who added this user
        joined_at: When user was added
        last_active_at: Last activity in project
    """

    __tablename__ = "project_stakeholder_links"

    # ==================== Composite Primary Key ====================

    project_id: int = Field(
        foreign_key="projects.id",
        primary_key=True,
        ondelete="CASCADE",
        description="Project ID",
    )

    user_id: int = Field(
        foreign_key="users.id",
        primary_key=True,
        ondelete="CASCADE",
        description="User ID",
    )

    # ==================== Role ====================

    role: ProjectRole = Field(
        default=ProjectRole.VIEWER,
        index=True,
        description="User's role in this project",
    )

    # ==================== Metadata ====================

    added_by_id: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        description="User ID who added this member",
    )

    # ==================== Timestamps ====================

    joined_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        description="When user was added to project (UTC)",
    )

    last_active_at: Optional[datetime] = Field(
        default=None,
        description="Last time user was active in this project",
    )

    # ==================== Relationships ====================

    project: "Project" = Relationship(
        back_populates="stakeholder_links",
        sa_relationship_kwargs={
            "lazy": "joined",
        },
    )

    user: "User" = Relationship(
        back_populates="stakeholder_links",
        sa_relationship_kwargs={
            "lazy": "joined",
            "foreign_keys": "[ProjectStakeholderLink.user_id]",
        },
    )

    added_by: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "lazy": "joined",
            "foreign_keys": "[ProjectStakeholderLink.added_by_id]",
        },
    )

    # ==================== Indexes ====================

    __table_args__ = (
        Index("idx_link_project_role", "project_id", "role"),
        Index("idx_link_user_projects", "user_id", "joined_at"),
    )

    # ==================== Helper Methods ====================

    @property
    def can_edit(self) -> bool:
        """Check if this member can edit project content."""
        return self.role.can_edit

    @property
    def can_manage(self) -> bool:
        """Check if this member can manage project settings."""
        return self.role.can_manage

    @property
    def can_delete(self) -> bool:
        """Check if this member can delete the project."""
        return self.role.can_delete

    def update_last_active(self) -> None:
        """Record member activity."""
        self.last_active_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<ProjectStakeholderLink("
            f"project_id={self.project_id}, "
            f"user_id={self.user_id}, "
            f"role={self.role.value}"
            f")>"
        )
