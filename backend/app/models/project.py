"""
Project and HistoricalDocument models.

Project represents a software architecture project with associated documentation,
proposals, and stakeholders. HistoricalDocument stores uploaded documents that
are processed by the RAG pipeline for AI-powered analysis.

Relationships:
    Project:
        - owner: User who created the project
        - members: Users who are stakeholders
        - historical_documents: Uploaded documents
        - proposals: Architecture proposals generated
        - stakeholder_links: Many-to-many links to stakeholders
        - analysis_stakeholders: AI-defined stakeholder personas

    HistoricalDocument:
        - project: Parent project
        - chunks: Text chunks for vector search (RAG)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship, Column, Text, String
from sqlalchemy import Index

from app.models.links import ProjectStakeholderLink

if TYPE_CHECKING:
    from app.models.chunk import DocumentChunk
    from app.models.proposal import Proposal
    from app.models.stakeholder import Stakeholder
    from app.models.user import User


# ==================== Enums ====================


class DocumentStatus(str, Enum):
    """
    Document processing status.

    States:
        PENDING: Uploaded, awaiting processing
        PROCESSING: Currently being chunked/vectorized
        COMPLETED: Successfully processed and indexed
        FAILED: Processing failed (see error logs)
    """

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    @classmethod
    def default(cls) -> "DocumentStatus":
        """Get default status for new documents."""
        return cls.PENDING


class ProjectVisibility(str, Enum):
    """
    Project visibility settings.

    Levels:
        PRIVATE: Only owner and members can access
        TEAM: All users in organization can view
        PUBLIC: Anyone can view (read-only)
    """

    PRIVATE = "private"
    TEAM = "team"
    PUBLIC = "public"

    @classmethod
    def default(cls) -> "ProjectVisibility":
        """Get default visibility for new projects."""
        return cls.PRIVATE


# ==================== Project Model ====================


class Project(SQLModel, table=True):
    """
    Software architecture project.

    Central entity that groups together documents, proposals, stakeholders,
    and AI-generated architecture recommendations.

    Attributes:
        id: Primary key
        name: Project name/title
        description: Project description (optional)
        visibility: Access control level
        is_archived: Soft delete flag
        owner_id: Foreign key to creating user
        created_at: Project creation timestamp
        updated_at: Last modification timestamp
        last_activity_at: Last activity (upload, proposal, etc.)
    """

    __tablename__ = "projects"

    # ==================== Primary Key ====================

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Project ID",
    )

    # ==================== Core Fields ====================

    name: str = Field(
        index=True,
        min_length=1,
        max_length=200,
        nullable=False,
        description="Project name/title",
    )

    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        sa_column=Column(Text),
        description="Project description (Markdown supported)",
    )

    # ==================== Access Control ====================

    visibility: ProjectVisibility = Field(
        default=ProjectVisibility.PRIVATE,
        description="Project visibility level",
    )

    is_archived: bool = Field(
        default=False,
        description="Soft delete flag (archived projects hidden from UI)",
    )

    # ==================== Ownership ====================

    owner_id: int = Field(
        foreign_key="users.id",
        index=True,
        description="ID of user who created this project",
    )

    # ==================== Metadata ====================

    tags: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Comma-separated tags for filtering (e.g., 'microservices,payment,fintech')",
    )

    tech_stack: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Technologies used (e.g., 'Python,PostgreSQL,FastAPI')",
    )

    # ==================== Statistics ====================

    document_count: int = Field(
        default=0,
        description="Cached count of uploaded documents",
    )

    proposal_count: int = Field(
        default=0,
        description="Cached count of generated proposals",
    )

    member_count: int = Field(
        default=0,
        description="Cached count of stakeholders/members",
    )

    # ==================== Timestamps ====================

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
        description="Project creation timestamp (UTC)",
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc).replace(tzinfo=None)
        },
        description="Last update timestamp (UTC)",
    )

    last_activity_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
        description="Last activity timestamp (upload, proposal, debate, etc.)",
    )

    archived_at: Optional[datetime] = Field(
        default=None,
        description="When project was archived (null if active)",
    )

    # ==================== Relationships ====================

    owner: "User" = Relationship(
        back_populates="owned_projects",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    historical_documents: List["HistoricalDocument"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
            "order_by": "HistoricalDocument.upload_date.desc()",
        },
    )

    proposals: List["Proposal"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
            "order_by": "Proposal.created_at.desc()",
        },
    )

    stakeholder_links: List["ProjectStakeholderLink"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
        },
    )

    analysis_stakeholders: List["Stakeholder"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={
            "lazy": "joined",
            "cascade": "all, delete-orphan",
        },
    )

    # ==================== Indexes ====================

    __table_args__ = (
        Index("idx_project_owner_created", "owner_id", "created_at"),
        Index("idx_project_archived_activity", "is_archived", "last_activity_at"),
        Index("idx_project_visibility", "visibility", "is_archived"),
    )

    # ==================== Helper Methods ====================

    @property
    def members(self) -> List["User"]:
        return [link.user for link in self.stakeholder_links]

    @property
    def is_active(self) -> bool:
        """Check if project is active (not archived)."""
        return not self.is_archived

    @property
    def tag_list(self) -> List[str]:
        """Get tags as list."""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]

    @property
    def tech_stack_list(self) -> List[str]:
        """Get tech stack as list."""
        if not self.tech_stack:
            return []
        return [tech.strip() for tech in self.tech_stack.split(",") if tech.strip()]

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def archive(self) -> None:
        """Archive this project (soft delete)."""
        self.is_archived = True
        self.archived_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def unarchive(self) -> None:
        """Restore archived project."""
        self.is_archived = False
        self.archived_at = None
        self.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def is_member(self, user_id: int) -> bool:
        """
        Check if user is project member (owner or stakeholder).

        Args:
            user_id: User ID to check

        Returns:
            bool: True if user is owner or stakeholder
        """
        if self.owner_id == user_id:
            return True
        return any(link.user_id == user_id for link in self.stakeholder_links)

    def increment_document_count(self) -> None:
        """Increment cached document count."""
        self.document_count += 1
        self.update_activity()

    def increment_proposal_count(self) -> None:
        """Increment cached proposal count."""
        self.proposal_count += 1
        self.update_activity()

    def decrement_proposal_count(self) -> None:
        """Decrement cached proposal count, clamped at zero."""
        if self.proposal_count > 0:
            self.proposal_count -= 1
        self.update_activity()

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<Project(id={self.id}, name={self.name!r}, owner_id={self.owner_id})>"

    def __str__(self) -> str:
        """Human-readable string representation."""
        return self.name


# ==================== HistoricalDocument Model ====================


class HistoricalDocument(SQLModel, table=True):
    """
    Uploaded document for RAG (Retrieval-Augmented Generation) pipeline.

    Documents are processed into chunks for vector search, enabling AI agents
    to reference project-specific context during debates and proposal generation.

    Attributes:
        id: Primary key
        filename: Original filename
        content_text: Extracted text content
        file_size_bytes: File size in bytes
        mime_type: MIME type (e.g., 'application/pdf')
        upload_date: Upload timestamp
        processed_at: When processing completed
        status: Processing status (pending/processing/completed/failed)
        indexing_progress: Percentage of processing completed (0-100)
        error_message: Error details if processing failed
        chunk_count: Number of chunks created
        project_id: Foreign key to parent project
    """

    __tablename__ = "historical_documents"

    # ==================== Primary Key ====================

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Document ID",
    )

    # ==================== File Metadata ====================

    filename: str = Field(
        max_length=255,
        sa_column=Column(String(255), nullable=False),
        description="Original filename",
    )

    file_size_bytes: Optional[int] = Field(
        default=None,
        description="File size in bytes",
    )

    mime_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="MIME type (e.g., 'application/pdf', 'text/plain')",
    )

    # ==================== Content ====================

    content_text: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="Extracted text content (null until processed)",
    )

    # ==================== Processing Status ====================

    status: DocumentStatus = Field(
        default=DocumentStatus.PENDING,
        index=True,
        description="Document processing status",
    )

    indexing_progress: int = Field(
        default=0,
        description="Processing progress percentage (0-100)",
    )

    error_message: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="Error message if processing failed",
    )

    # ==================== Statistics ====================

    chunk_count: int = Field(
        default=0,
        description="Number of chunks created for vector search",
    )

    character_count: int = Field(
        default=0,
        description="Total character count of extracted text",
    )

    # ==================== Timestamps ====================

    upload_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
        description="Upload timestamp (UTC)",
    )

    processed_at: Optional[datetime] = Field(
        default=None,
        description="When processing completed (null if pending/failed)",
    )

    # ==================== Foreign Keys ====================

    project_id: int = Field(
        foreign_key="projects.id",
        index=True,
        description="Parent project ID",
    )

    uploaded_by_id: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        description="User who uploaded this document",
    )

    # ==================== Relationships ====================

    project: "Project" = Relationship(
        back_populates="historical_documents",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    chunks: List["DocumentChunk"] = Relationship(
        back_populates="document",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
        },
    )

    # ==================== Indexes ====================

    __table_args__ = (
        Index("idx_document_project_status", "project_id", "status"),
        Index("idx_document_upload_date", "upload_date"),
        Index("idx_document_status_processed", "status", "processed_at"),
    )

    # ==================== Helper Methods ====================

    @property
    def is_processed(self) -> bool:
        """Check if document has been successfully processed."""
        return self.status == DocumentStatus.COMPLETED

    @property
    def is_pending(self) -> bool:
        """Check if document is pending processing."""
        return self.status == DocumentStatus.PENDING

    @property
    def is_processing(self) -> bool:
        """Check if document is currently being processed."""
        return self.status == DocumentStatus.PROCESSING

    @property
    def has_failed(self) -> bool:
        """Check if document processing failed."""
        return self.status == DocumentStatus.FAILED

    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes."""
        if not self.file_size_bytes:
            return 0.0
        return self.file_size_bytes / (1024 * 1024)

    @property
    def file_extension(self) -> str:
        """Get file extension from filename."""
        if "." not in self.filename:
            return ""
        return "." + self.filename.rsplit(".", 1)[-1].lower()

    def mark_processing(self) -> None:
        """Mark document as currently processing."""
        self.status = DocumentStatus.PROCESSING

    def mark_completed(self, chunk_count: int) -> None:
        """
        Mark document as successfully processed.

        Args:
            chunk_count: Number of chunks created
        """
        self.status = DocumentStatus.COMPLETED
        self.chunk_count = chunk_count
        self.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.error_message = None

    def mark_failed(self, error: str) -> None:
        """
        Mark document processing as failed.

        Args:
            error: Error message
        """
        self.status = DocumentStatus.FAILED
        self.error_message = error
        self.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def calculate_character_count(self) -> None:
        """Calculate and store character count from content_text."""
        if self.content_text:
            self.character_count = len(self.content_text)
        else:
            self.character_count = 0

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<HistoricalDocument(id={self.id}, filename={self.filename!r}, status={self.status.value})>"

    def __str__(self) -> str:
        """Human-readable string representation."""
        return self.filename
