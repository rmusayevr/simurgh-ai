"""
Debate session models.

Tracks multi-agent debates where AI personas (Legacy Keeper, Innovator, Mediator)
discuss architecture trade-offs and negotiate consensus.

Models:
    - DebateSession: Complete debate session record
    - DebateTurn: Individual turn in debate (embedded)

Relationships:
    DebateSession -> Proposal (one debate per proposal)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, JSON, Column, Relationship
from sqlalchemy import Index

if TYPE_CHECKING:
    from app.models.proposal import Proposal


# ==================== Enums ====================


class ConsensusType(str, Enum):
    """
    Type of consensus reached.

    Types:
        UNANIMOUS: All agents fully agree
        MAJORITY: 2 out of 3 agents agree
        COMPROMISE: Mediator synthesized middle ground
        TIMEOUT: No consensus, time limit reached
    """

    UNANIMOUS = "UNANIMOUS"
    MAJORITY = "MAJORITY"
    COMPROMISE = "COMPROMISE"
    TIMEOUT = "TIMEOUT"


# ==================== Embedded Models ====================


class DebateTurn(SQLModel):
    """
    Single turn in a multi-agent debate (not a table, embedded in JSONB).

    Attributes:
        turn_number: Sequential turn number (1, 2, 3...)
        persona: Agent persona speaking (legacy_keeper, innovator, mediator)
        response: Agent's response text
        timestamp: When this turn occurred
        sentiment: Detected sentiment (agreeable/contentious/neutral)
        key_points: Extracted key arguments
    """

    turn_number: int = Field(
        description="Sequential turn number",
    )

    persona: str = Field(
        description="AI persona (legacy_keeper/innovator/mediator)",
    )

    response: str = Field(
        description="Agent's response text",
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        description="Turn timestamp (UTC)",
    )

    sentiment: Optional[str] = Field(
        default=None,
        description="Detected sentiment (agreeable/contentious/neutral)",
    )

    key_points: List[str] = Field(
        default=[],
        description="Extracted key arguments from this turn",
    )


# ==================== DebateSession Model ====================


class DebateSession(SQLModel, table=True):
    """
    Multi-agent debate session record.

    Captures a complete debate between AI personas about an architecture proposal,
    including all turns, final consensus, and performance metrics.

    Attributes:
        id: Primary key (UUID)
        proposal_id: Parent proposal (FK)
        debate_history: Complete turn-by-turn debate record (JSONB)
        final_consensus_proposal: Synthesized final recommendation
        consensus_reached: Whether consensus was achieved
        consensus_type: Type of consensus (unanimous/majority/compromise)
        total_turns: Number of debate turns
        duration_seconds: Total debate duration
        conflict_density: Ratio of contentious turns (0.0-1.0)
        legacy_keeper_consistency: Persona consistency score
        innovator_consistency: Persona consistency score
        mediator_consistency: Persona consistency score
        started_at: Debate start timestamp
        completed_at: Debate completion timestamp
    """

    __tablename__ = "debate_sessions"

    # ==================== Primary Key ====================

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Debate session ID (UUID)",
    )

    # ==================== Foreign Keys ====================

    proposal_id: int = Field(
        foreign_key="proposals.id",
        index=True,
        description="Parent proposal ID",
    )

    # ==================== Debate Content ====================

    debate_history: List[Dict[str, Any]] = Field(
        default=[],
        sa_column=Column(JSON),
        description="Complete turn-by-turn debate record",
    )

    final_consensus_proposal: Optional[str] = Field(
        default=None,
        description="Final synthesized recommendation (Markdown)",
    )

    # ==================== Consensus Metrics ====================

    consensus_reached: bool = Field(
        default=False,
        description="Whether consensus was achieved",
    )

    consensus_confidence: Optional[float] = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Model confidence in consensus (0.0-1.0)",
    )

    consensus_type: Optional[ConsensusType] = Field(
        default=None,
        description="Type of consensus reached",
    )

    # ==================== Performance Metrics ====================

    total_turns: int = Field(
        default=0,
        description="Number of debate turns",
    )

    duration_seconds: float = Field(
        default=0.0,
        description="Total debate duration in seconds",
    )

    conflict_density: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Ratio of contentious turns (0.0-1.0)",
    )

    # ==================== Persona Consistency Scores ====================
    # Used for RQ2 (Persona Consistency) in thesis

    legacy_keeper_consistency: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Legacy Keeper persona consistency (0.0-1.0)",
    )

    innovator_consistency: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Innovator persona consistency (0.0-1.0)",
    )

    mediator_consistency: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Mediator persona consistency (0.0-1.0)",
    )

    overall_persona_consistency: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Average persona consistency across all agents",
    )

    # ==================== Timestamps ====================

    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
        description="Debate start timestamp (UTC)",
    )

    completed_at: Optional[datetime] = Field(
        default=None,
        description="Debate completion timestamp (UTC)",
    )

    # ==================== Relationships ====================

    proposal: Optional["Proposal"] = Relationship(
        back_populates="debate_sessions",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    # ==================== Indexes ====================

    __table_args__ = (
        Index("idx_debate_proposal", "proposal_id"),
        Index("idx_debate_consensus", "consensus_reached", "completed_at"),
        Index("idx_debate_started", "started_at"),
    )

    # ==================== Configuration ====================

    class Config:
        arbitrary_types_allowed = True

    # ==================== Helper Methods ====================

    @property
    def is_completed(self) -> bool:
        """Check if debate has completed."""
        return self.completed_at is not None

    @property
    def duration_minutes(self) -> float:
        """Get duration in minutes."""
        return self.duration_seconds / 60.0

    @property
    def average_turn_duration(self) -> float:
        """Get average seconds per turn."""
        if self.total_turns == 0:
            return 0.0
        return self.duration_seconds / self.total_turns

    @property
    def is_high_conflict(self) -> bool:
        """Check if debate had high conflict (>0.5 density)."""
        return self.conflict_density > 0.5

    def add_turn(
        self,
        persona: str,
        response: str,
        sentiment: Optional[str] = None,
        key_points: Optional[List[str]] = None,
        bias_alignment_score: float = 0.0,
    ) -> None:
        """
        Add a turn to debate history.

        Args:
            persona: AI persona name
            response: Agent response text
            sentiment: Optional sentiment (agreeable/contentious/neutral)
            key_points: Optional extracted key arguments
            bias_alignment_score: Persona consistency metric (0.0-1.0)
        """
        if self.debate_history is None:
            self.debate_history = []

        turn = {
            "turn_number": len(self.debate_history) + 1,
            "persona": persona,
            "response": response,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sentiment": sentiment,
            "key_points": key_points or [],
            "bias_alignment_score": bias_alignment_score,
        }

        self.debate_history.append(turn)
        self.total_turns = len(self.debate_history)

    def complete(
        self,
        consensus_reached: bool,
        consensus_type: Optional[ConsensusType] = None,
        final_proposal: Optional[str] = None,
    ) -> None:
        """
        Mark debate as completed.

        Args:
            consensus_reached: Whether consensus was achieved
            consensus_type: Type of consensus
            final_proposal: Final synthesized recommendation
        """
        self.consensus_reached = consensus_reached
        self.consensus_type = consensus_type
        self.final_consensus_proposal = final_proposal
        self.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # Calculate duration
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = delta.total_seconds()

    def calculate_persona_consistency(self) -> None:
        """Calculate overall persona consistency score."""
        scores = [
            self.legacy_keeper_consistency,
            self.innovator_consistency,
            self.mediator_consistency,
        ]

        # Filter out zero scores (personas that didn't participate)
        non_zero_scores = [s for s in scores if s > 0]

        if non_zero_scores:
            self.overall_persona_consistency = sum(non_zero_scores) / len(
                non_zero_scores
            )
        else:
            self.overall_persona_consistency = 0.0

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<DebateSession(id={self.id}, turns={self.total_turns}, consensus={self.consensus_reached})>"
