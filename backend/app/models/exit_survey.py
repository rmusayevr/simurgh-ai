"""
Exit Survey model for thesis evaluation.

Captures post-experiment comparative preferences and overall experience ratings
after participants have completed both experimental conditions.

Research Context:
    Used in Chapter 5 Section 5.3.3 ("Participant Preferences").
    Collected AFTER both scenarios to avoid priming effects.
    The preferred_system question deliberately avoids labelling which was
    baseline vs multi-agent until the debrief screen (post-submission).

One record per participant (enforced by unique constraint on participant_id).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Column, Text
from sqlalchemy import Index


# ==================== Enums ====================


class PreferredSystem(str, Enum):
    """
    Participant's preferred AI system after experiencing both conditions.

    Labels deliberately avoid revealing condition identity until post-submission
    debrief to keep preference data unbiased.
    """

    FIRST = "first"
    SECOND = "second"
    NO_PREFERENCE = "no_preference"
    NOT_SURE = "not_sure"


class FatigueLevel(str, Enum):
    """
    Self-reported fatigue / attention level during the study.
    Used as a data-quality covariate in Chapter 5 analysis.
    """

    NONE = "none"
    A_LITTLE = "a_little"
    YES_SIGNIFICANTLY = "yes_significantly"


# ==================== Model ====================


class ExitSurvey(SQLModel, table=True):
    """
    Post-experiment exit survey response.

    Collected once per participant immediately after they submit the second
    TrustQuestionnaire. Cannot be skipped; the debrief text is only shown
    after the record is persisted.

    Thesis Mapping:
        preferred_system         → Chapter 5 Section 5.3.3 (RQ3 preference data)
        preference_reasoning     → Qualitative theme analysis
        interface_rating         → Overall UX satisfaction covariate
        experienced_fatigue      → Data-quality / validity flag
        technical_issues         → Research-ops note (excluded responses)
        additional_feedback      → Open researcher notes

    Attributes:
        id: Primary key (UUID)
        participant_id: FK to participants.id (unique — one survey per person)
        preferred_system: Which system the participant preferred
        preference_reasoning: Open-ended reasoning text
        interface_rating: Overall experience Likert 1–7
        experienced_fatigue: Self-reported attention/fatigue level
        technical_issues: Optional description of any technical problems
        additional_feedback: Optional open-ended additional comments
        submitted_at: UTC timestamp of submission
    """

    __tablename__ = "exit_surveys"

    # ==================== Primary Key ====================

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Exit survey record ID (UUID)",
    )

    # ==================== Participant Link ====================

    participant_id: int = Field(
        foreign_key="participants.id",
        unique=True,  # One exit survey per participant
        nullable=False,
        index=True,
        description="FK to participants table — one survey per participant",
    )

    # ==================== Preference ====================

    preferred_system: PreferredSystem = Field(
        nullable=False,
        description="Which system participant preferred (first/second/no_preference/not_sure)",
    )

    preferred_system_actual: Optional[str] = Field(
        default=None,
        max_length=20,
        description=(
            "Resolved preferred system: 'baseline', 'multiagent', 'no_preference', or 'not_sure'. "
            "Derived at submission time from preferred_system + participant condition_order. "
            "Primary field for RQ3 statistical analysis — use this, not preferred_system_raw."
        ),
    )

    preference_reasoning: str = Field(
        sa_column=Column(Text, nullable=False),
        description="Open-ended: why did you prefer that system?",
    )

    # ==================== Overall Experience ====================

    interface_rating: int = Field(
        nullable=False,
        ge=1,
        le=7,
        description="Overall interface experience Likert 1–7",
    )

    # ==================== Fatigue ====================

    experienced_fatigue: FatigueLevel = Field(
        nullable=False,
        description="Self-reported fatigue level (none/a_little/yes_significantly)",
    )

    # ==================== Optional Feedback ====================

    technical_issues: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Optional: any technical problems encountered",
    )

    additional_feedback: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Optional: any other comments",
    )

    # ==================== Timestamps ====================

    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
        description="UTC timestamp of submission",
    )

    # ==================== Indexes ====================

    __table_args__ = (
        Index("idx_exit_survey_participant", "participant_id"),
        Index("idx_exit_survey_submitted", "submitted_at"),
        Index("idx_exit_survey_preferred_system", "preferred_system"),
    )

    # ==================== Properties ====================

    @property
    def preferred_first(self) -> bool:
        return self.preferred_system == PreferredSystem.FIRST

    @property
    def preferred_second(self) -> bool:
        return self.preferred_system == PreferredSystem.SECOND

    @property
    def has_clear_preference(self) -> bool:
        return self.preferred_system in (PreferredSystem.FIRST, PreferredSystem.SECOND)

    def to_analysis_dict(self) -> dict:
        """Flat dict for CSV/SPSS export (Chapter 5)."""
        return {
            "participant_id": self.participant_id,
            "preferred_system": self.preferred_system.value,
            "interface_rating": self.interface_rating,
            "experienced_fatigue": self.experienced_fatigue.value,
            "has_technical_issues": self.technical_issues is not None,
            "submitted_at": self.submitted_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"<ExitSurvey("
            f"participant={self.participant_id}, "
            f"preferred={self.preferred_system.value}, "
            f"rating={self.interface_rating}"
            f")>"
        )
