# ==================== debate.py ====================

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from uuid import UUID


# ==================== Debate Turn Schemas ====================


class DebateTurnRead(BaseModel):
    """Single turn in a multi-agent debate."""

    turn_number: int
    persona: str
    response: str
    timestamp: str
    sentiment: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    # quality_attributes_mentioned is stored as key_points in the JSONB dict
    quality_attributes_mentioned: List[str] = Field(default_factory=list)
    # bias_alignment_score is a computed metric stored alongside the turn dict;
    # optional so existing JSONB rows without this field still deserialize cleanly.
    bias_alignment_score: float = 0.0


# ==================== Debate Session Schemas ====================


class DebateSessionListRead(BaseModel):
    """
    Lightweight debate session summary for list views.
    Excludes full debate_history to avoid large payloads.
    """

    id: UUID
    proposal_id: int
    consensus_reached: bool
    consensus_type: Optional["ConsensusType"]
    total_turns: int
    duration_seconds: float
    conflict_density: float
    overall_persona_consistency: float
    started_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    @property
    def is_high_conflict(self) -> bool:
        return self.conflict_density > 0.5

    @property
    def duration_minutes(self) -> float:
        return round(self.duration_seconds / 60.0, 2)


class DebateSessionRead(BaseModel):
    """
    Full debate session detail including complete turn-by-turn history.
    Used for the Deep-Dive Debate Mode view.
    """

    id: UUID
    proposal_id: int
    debate_history: List[DebateTurnRead] = Field(default_factory=list)
    final_consensus_proposal: Optional[str]
    consensus_reached: bool
    consensus_type: Optional["ConsensusType"]
    total_turns: int
    duration_seconds: float
    conflict_density: float

    # Thesis RQ2 — Persona Consistency Scores
    legacy_keeper_consistency: float
    innovator_consistency: float
    mediator_consistency: float
    overall_persona_consistency: float

    started_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    @property
    def is_high_conflict(self) -> bool:
        return self.conflict_density > 0.5

    @property
    def duration_minutes(self) -> float:
        return round(self.duration_seconds / 60.0, 2)

    @property
    def average_turn_duration(self) -> float:
        if self.total_turns == 0:
            return 0.0
        return round(self.duration_seconds / self.total_turns, 2)


class DebateSessionDetail(DebateSessionRead):
    turns: List[DebateTurnRead] = Field(default_factory=list)
    final_consensus_proposal: Optional[str] = None
    legacy_keeper_consistency: Optional[float] = None
    innovator_consistency: Optional[float] = None
    mediator_consistency: Optional[float] = None

    @classmethod
    def from_session(cls, session: "DebateSession") -> "DebateSessionDetail":
        """Build a DebateSessionDetail from a DebateSession ORM object,
        mapping debate_history → turns."""
        data = session.__dict__.copy()
        history = data.get("debate_history") or []
        turns = [DebateTurnRead(**t) if isinstance(t, dict) else t for t in history]
        data["turns"] = turns
        return cls.model_validate(data)


# ==================== Debate Request Schemas ====================


class StartDebateRequest(BaseModel):
    """Request schema for initiating a multi-agent debate on a proposal."""

    document_ids: List[int] = Field(
        default_factory=list,
        description="Historical document IDs to include as RAG context",
    )
    focus_areas: List[str] = Field(
        default=["Technical Feasibility", "Legal Compliance"],
        description="Specific areas for the agents to focus on",
    )


class DebateCompleteRequest(BaseModel):
    """
    Request schema for manually completing a debate session.
    Matches the model's complete() method.
    """

    consensus_reached: bool
    consensus_type: Optional["ConsensusType"] = None
    final_consensus_proposal: Optional[str] = Field(
        default=None,
        description="Final synthesized recommendation (Markdown)",
    )


class DebatePersonaConsistencyUpdate(BaseModel):
    """
    Schema for updating persona consistency scores after manual coding.
    Used in thesis RQ2 analysis workflow — triggered after PersonaCoding records
    are submitted for a debate session.
    """

    legacy_keeper_consistency: float = Field(ge=0.0, le=1.0)
    innovator_consistency: float = Field(ge=0.0, le=1.0)
    mediator_consistency: float = Field(ge=0.0, le=1.0)


from app.models.debate import ConsensusType, DebateSession

namespace = {"ConsensusType": ConsensusType}

DebateSessionListRead.model_rebuild(_types_namespace=namespace)
DebateSessionRead.model_rebuild(_types_namespace=namespace)
DebateSessionDetail.model_rebuild(_types_namespace=namespace)
DebateCompleteRequest.model_rebuild(_types_namespace=namespace)
