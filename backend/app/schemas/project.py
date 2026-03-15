from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime

from app.models.links import ProjectRole
from app.models.project import ProjectVisibility, DocumentStatus
from app.schemas.user import UserMinimalRead


if TYPE_CHECKING:
    from app.schemas.stakeholder import StakeholderRead

# ==================== Historical Document Schemas ====================


class HistoricalDocumentCreate(BaseModel):
    """Schema for document upload metadata (file content handled via multipart)."""

    filename: str = Field(min_length=1, max_length=255)


class HistoricalDocumentRead(BaseModel):
    """Full document record returned after upload or retrieval."""

    id: int
    filename: str
    file_size_bytes: Optional[int]
    mime_type: Optional[str]
    status: DocumentStatus
    chunk_count: int
    character_count: int
    upload_date: datetime
    processed_at: Optional[datetime]
    uploaded_by_id: Optional[int]
    project_id: int

    model_config = ConfigDict(from_attributes=True)

    @property
    def file_size_mb(self) -> float:
        if not self.file_size_bytes:
            return 0.0
        return round(self.file_size_bytes / (1024 * 1024), 2)

    @property
    def is_ready_for_rag(self) -> bool:
        """Whether this document is indexed and ready for RAG queries."""
        return self.status == DocumentStatus.COMPLETED and self.chunk_count > 0


class HistoricalDocumentMinimalRead(BaseModel):
    """Lightweight document summary for embedding in project list responses."""

    id: int
    filename: str
    status: DocumentStatus
    chunk_count: int
    upload_date: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== Project Member Schemas ====================


class ProjectMemberRead(BaseModel):
    """Project member with their role in this project."""

    user_id: int
    user: UserMinimalRead
    role: ProjectRole
    joined_at: datetime
    last_active_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ProjectMemberAdd(BaseModel):
    """Schema for adding a user to a project."""

    email: EmailStr
    role: ProjectRole = ProjectRole.VIEWER


class ProjectMemberUpdate(BaseModel):
    """Schema for updating a member's role."""

    role: ProjectRole


# ==================== Project Schemas ====================


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""

    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    visibility: ProjectVisibility = ProjectVisibility.PRIVATE
    tags: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Comma-separated tags (e.g., 'microservices,payment,fintech')",
    )
    tech_stack: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Comma-separated technologies (e.g., 'Python,FastAPI,PostgreSQL')",
    )

    @field_validator("tags", "tech_stack", mode="before")
    @classmethod
    def strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return ",".join(tag.strip() for tag in v.split(",") if tag.strip())
        return v


class ProjectUpdate(BaseModel):
    """Schema for updating project fields. All fields optional."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    visibility: Optional[ProjectVisibility] = None
    tags: Optional[str] = Field(default=None, max_length=500)
    tech_stack: Optional[str] = Field(default=None, max_length=500)

    @field_validator("tags", "tech_stack", mode="before")
    @classmethod
    def strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return ",".join(tag.strip() for tag in v.split(",") if tag.strip())
        return v


class ProjectListRead(BaseModel):
    """
    Lightweight project summary for list views.
    Avoids loading full documents and stakeholders.
    """

    id: int
    name: str
    description: Optional[str]
    visibility: ProjectVisibility
    is_archived: bool
    owner_id: int
    owner: Optional[UserMinimalRead]
    tags: Optional[str]
    tech_stack: Optional[str]
    document_count: int
    proposal_count: int
    member_count: int
    created_at: datetime
    last_activity_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @property
    def tag_list(self) -> List[str]:
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def tech_stack_list(self) -> List[str]:
        if not self.tech_stack:
            return []
        return [t.strip() for t in self.tech_stack.split(",") if t.strip()]


class ProjectRead(BaseModel):
    """
    Full project detail including members and documents.
    Used for the project detail page.
    """

    id: int
    name: str
    description: Optional[str]
    visibility: ProjectVisibility
    is_archived: bool
    owner_id: int
    owner: Optional[UserMinimalRead]
    tags: Optional[str]
    tech_stack: Optional[str]
    document_count: int
    proposal_count: int
    member_count: int
    stakeholder_links: List[ProjectMemberRead] = Field(default_factory=list)
    historical_documents: List[HistoricalDocumentMinimalRead] = Field(
        default_factory=list
    )
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    archived_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

    @property
    def tag_list(self) -> List[str]:
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def tech_stack_list(self) -> List[str]:
        if not self.tech_stack:
            return []
        return [t.strip() for t in self.tech_stack.split(",") if t.strip()]


class ProjectReadDetail(ProjectRead):
    """
    Extended project detail including AI-analyzed stakeholders.
    Used for the full project dashboard view.
    Imported lazily to avoid circular import with stakeholder schemas.
    """

    analysis_stakeholders: List["StakeholderRead"] = Field(default_factory=list)
    historical_documents: List[HistoricalDocumentRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ==================== Project Archive Schemas ====================


class ProjectArchiveResponse(BaseModel):
    """Response returned after archiving or restoring a project."""

    id: int
    name: str
    is_archived: bool
    archived_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class DocumentIndexingStatus(BaseModel):
    document_id: int
    filename: str
    status: DocumentStatus
    chunk_count: int
    indexing_progress: int
    error_message: Optional[str]
    is_ready_for_rag: bool


class HistoricalDocumentDetail(HistoricalDocumentRead):
    content_text: Optional[str] = None
