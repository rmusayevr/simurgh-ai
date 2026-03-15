from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.models.proposal import ProposalStatus, ApprovalStatus, AgentPersona
from app.schemas.user import UserMinimalRead


# ==================== Chat Schemas ====================


class ChatMessage(BaseModel):
    """Single message in a chat history."""

    role: str = Field(description="Message role: 'user' or 'assistant'")
    content: str
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    """Request schema for chatting with a proposal variation's AI persona."""

    message: str = Field(min_length=1, max_length=10000)
    history: List[ChatMessage] = Field(default_factory=list)


# ==================== Task Document Schemas ====================


class TaskDocumentRead(BaseModel):
    """Task-specific document attached to a proposal."""

    id: int
    filename: str
    file_size_bytes: Optional[int]
    mime_type: Optional[str]
    uploaded_at: datetime
    uploader: Optional[UserMinimalRead] = None

    model_config = ConfigDict(from_attributes=True)

    @property
    def file_size_mb(self) -> float:
        if not self.file_size_bytes:
            return 0.0
        return round(self.file_size_bytes / (1024 * 1024), 2)


# ==================== Proposal Variation Schemas ====================


class ProposalVariationMinimalRead(BaseModel):
    """
    Lightweight variation summary for embedding in proposal list views.
    Excludes heavy fields like structured_prd and chat_history.
    """

    id: int
    agent_persona: AgentPersona
    confidence_score: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @property
    def persona_display_name(self) -> str:
        return self.agent_persona.value.replace("_", " ").title()

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence_score > 70


class ProposalVariationRead(BaseModel):
    """Full variation detail including generated PRD and chat history."""

    id: int
    agent_persona: AgentPersona
    structured_prd: str
    reasoning: Optional[str]
    trade_offs: Optional[str]
    confidence_score: int
    chat_history: List[Dict[str, Any]] = Field(default_factory=list)
    proposal_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @property
    def persona_display_name(self) -> str:
        return self.agent_persona.value.replace("_", " ").title()

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence_score > 70


# ==================== Proposal Schemas ====================


class ProposalCreateDraft(BaseModel):
    """Schema for creating a new proposal draft."""

    project_id: int
    task_description: str = Field(min_length=10, max_length=10000)


class ProposalListRead(BaseModel):
    """
    Lightweight proposal summary for list views.
    Avoids loading full PRD content, variations, and documents.
    """

    id: int
    project_id: int
    task_description: str
    status: ProposalStatus
    approval_status: ApprovalStatus
    selected_variation_id: Optional[int]
    created_by_id: Optional[int]
    variation_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProposalRead(BaseModel):
    """Full proposal detail including variations, documents, and approval info."""

    id: int
    project_id: int
    task_description: str
    structured_prd: Optional[str]
    status: ProposalStatus
    approval_status: ApprovalStatus
    error_message: Optional[str]
    selected_variation_id: Optional[int]
    created_by_id: Optional[int]
    approved_by_id: Optional[int]
    approved_at: Optional[datetime]
    variations: List[ProposalVariationRead] = Field(default_factory=list)
    task_documents: List[TaskDocumentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @property
    def is_completed(self) -> bool:
        return self.status == ProposalStatus.COMPLETED

    @property
    def is_approved(self) -> bool:
        return self.approval_status == ApprovalStatus.APPROVED

    @property
    def has_selected_variation(self) -> bool:
        return self.selected_variation_id is not None


# ==================== Proposal Action Schemas ====================


class SelectVariationRequest(BaseModel):
    """Request to select a variation as the chosen approach."""

    variation_id: int


class ProposalApproveRequest(BaseModel):
    """Request to approve a proposal (admin/manager only)."""

    approved_by_id: int


class ProposalRejectRequest(BaseModel):
    """Request to reject a proposal with a reason."""

    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional reason for rejection",
    )


class ProposalRevisionRequest(BaseModel):
    """Request to mark a proposal as needing revision."""

    feedback: str = Field(
        min_length=10,
        max_length=2000,
        description="Feedback describing what needs to change",
    )


class ProposalStatusResponse(BaseModel):
    """Lightweight response after a status or approval change."""

    id: int
    status: ProposalStatus
    approval_status: ApprovalStatus
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BaselineProposalRequest(BaseModel):
    proposal_id: int


class ChatResponse(BaseModel):
    """Response schema for a chat message from the proposal's AI persona."""

    response: str
    reasoning: Optional[str]
    trade_offs: Optional[str]
    confidence_score: int
    updated_history: List[Dict[str, Any]] = Field(default_factory=list)
