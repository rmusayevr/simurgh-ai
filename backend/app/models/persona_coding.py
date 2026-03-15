"""
Persona coding model for thesis RQ2 validation.

Stores manual coding results used to verify AI persona consistency
in multi-agent debate sessions. Used in RQ2 (Persona Consistency) analysis.

Research Context:
    RQ2: "Do AI personas maintain consistent character throughout debates?"

    Methodology:
        - Manually code 20% of debate turns
        - Verify persona stays in character
        - Check quality attributes mentioned
        - Flag hallucinations or character breaks
        - Calculate inter-rater reliability (if multiple coders)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import Index


# ==================== Enums ====================


class InCharacterRating(str, Enum):
    """
    Rating for persona character consistency.

    Values:
        YES: Persona fully in character throughout turn
        PARTIAL: Mostly in character with minor deviations
        NO: Clear character break or wrong persona behavior
    """

    YES = "yes"
    PARTIAL = "partial"
    NO = "no"

    @property
    def consistency_score(self) -> float:
        """Numeric score for quantitative analysis."""
        return {
            InCharacterRating.YES: 1.0,
            InCharacterRating.PARTIAL: 0.5,
            InCharacterRating.NO: 0.0,
        }[self]


class HallucinationRating(str, Enum):
    """
    Rating for factual accuracy / hallucination severity.

    Values:
        NONE: No hallucinations detected
        MINOR: Small inaccuracies that don't affect core argument
        MAJOR: Significant fabrications that undermine credibility
    """

    NONE = "no"
    MINOR = "minor"
    MAJOR = "major"

    @property
    def severity_score(self) -> float:
        """Numeric score (higher = worse)."""
        return {
            HallucinationRating.NONE: 0.0,
            HallucinationRating.MINOR: 0.5,
            HallucinationRating.MAJOR: 1.0,
        }[self]


# ==================== Model ====================


class PersonaCoding(SQLModel, table=True):
    """
    Manual coding record for thesis RQ2 validation.

    Each record represents a human coder's assessment of one
    AI persona turn in a debate session.

    Used to calculate:
        - Persona consistency rate (% of YES + PARTIAL)
        - Hallucination rate (% with MINOR or MAJOR)
        - Quality attribute coverage (which attributes mentioned)
        - Inter-rater reliability (if multiple coders used)

    Thesis Usage:
        - Code 20% sample of debate turns
        - Calculate consistency metrics for RQ2
        - Present in Chapter 5 (Results)
        - Defend in thesis presentation

    Attributes:
        id: Primary key (UUID)
        debate_id: FK to debate session being coded
        turn_index: Which turn (0-indexed) within debate
        persona: Which persona was speaking
        in_character: Consistency rating (yes/partial/no)
        quality_attributes: List of quality attributes mentioned
        hallucination: Hallucination severity rating
        bias_alignment: Whether response matches persona's bias
        notes: Coder's qualitative observations
        coder_id: FK to user performing the coding
        created_at: Coding timestamp
        updated_at: Last edit timestamp
    """

    __tablename__ = "persona_codings"

    # ==================== Primary Key ====================

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Coding record ID",
    )

    # ==================== Debate Context ====================

    debate_id: UUID = Field(
        index=True,
        nullable=False,
        description="Debate session being coded",
    )

    turn_index: int = Field(
        nullable=False,
        ge=0,
        description="0-indexed turn number within debate",
    )

    persona: str = Field(
        max_length=50,
        nullable=False,
        description="Persona being coded (legacy_keeper/innovator/mediator)",
    )

    # ==================== RQ2 Coding Variables ====================

    in_character: InCharacterRating = Field(
        nullable=False,
        description="Persona consistency rating (yes/partial/no)",
    )

    quality_attributes: List[str] = Field(
        default=[],
        sa_column=Column(JSON),
        description="Quality attributes mentioned in this turn",
    )

    hallucination: HallucinationRating = Field(
        default=HallucinationRating.NONE,
        description="Hallucination severity (no/minor/major)",
    )

    bias_alignment: bool = Field(
        default=True,
        description="Whether response aligns with persona's decision bias",
    )

    # ==================== Qualitative Notes ====================

    notes: Optional[str] = Field(
        default=None,
        description="Coder's qualitative observations about this turn",
    )

    evidence_quote: Optional[str] = Field(
        default=None,
        description="Direct quote from turn supporting the coding decision",
    )

    # ==================== Metadata ====================

    coder_id: int = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        description="User who performed this coding",
    )

    coding_duration_seconds: Optional[int] = Field(
        default=None,
        description="Time spent coding this turn (for research transparency)",
    )

    # ==================== Timestamps ====================

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
        description="Coding timestamp (UTC)",
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc).replace(tzinfo=None)
        },
        description="Last edit timestamp (UTC)",
    )

    # ==================== Indexes ====================

    __table_args__ = (
        Index("idx_coding_debate_turn", "debate_id", "turn_index"),
        Index("idx_coding_persona", "persona", "in_character"),
        Index("idx_coding_coder", "coder_id", "created_at"),
    )

    # ==================== Helper Methods ====================

    @property
    def consistency_score(self) -> float:
        """
        Numeric consistency score for quantitative analysis.

        Returns:
            float: 1.0 (yes) / 0.5 (partial) / 0.0 (no)
        """
        return self.in_character.consistency_score

    @property
    def hallucination_score(self) -> float:
        """
        Numeric hallucination severity score.

        Returns:
            float: 0.0 (none) / 0.5 (minor) / 1.0 (major)
        """
        return self.hallucination.severity_score

    @property
    def quality_attribute_count(self) -> int:
        """Number of quality attributes mentioned."""
        return len(self.quality_attributes)

    @property
    def is_fully_consistent(self) -> bool:
        """Check if persona was fully in character."""
        return self.in_character == InCharacterRating.YES

    @property
    def has_hallucination(self) -> bool:
        """Check if any hallucination was detected."""
        return self.hallucination != HallucinationRating.NONE

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<PersonaCoding("
            f"debate_id={self.debate_id}, "
            f"turn={self.turn_index}, "
            f"persona={self.persona}, "
            f"in_character={self.in_character.value}"
            f")>"
        )
