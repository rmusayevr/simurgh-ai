"""
Questionnaire response model for thesis evaluation.

Stores participant responses for empirical evaluation of the multi-agent
AI system. Maps to the Trust Questionnaire defined in thesis Chapter 3.

Research Context:
    RQ1: "Do multi-agent proposals achieve higher trust scores?"
    RQ3: "Do participants prefer multi-agent over single-agent output?"

    Methodology:
        - Within-subject A/B design (each participant sees both conditions)
        - Counterbalanced order (50% baseline-first, 50% multiagent-first)
        - 7-point Likert scales for quantitative analysis
        - Open-ended questions for qualitative themes
        - Paired t-test to compare trust scores

Data Collection:
    - N = 5-10 participants (MSc students or 2+ years experience)
    - 2 scenarios per participant (counterbalanced)
    - Both baseline and multi-agent conditions
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Column, Text
from sqlalchemy import Index


# ==================== Enums ====================


class ExperimentCondition(str, Enum):
    """
    Experimental condition for A/B comparison.

    Conditions:
        BASELINE: Single-agent LLM response (control)
        MULTIAGENT: Council of Agents debate (treatment)
    """

    BASELINE = "BASELINE"
    MULTIAGENT = "MULTIAGENT"


class ScenarioID(int, Enum):
    """
    Predefined evaluation scenarios.

    Scenarios:
        PAYMENT: E-commerce payment service migration
        ANALYTICS: Real-time analytics pipeline
        AUTH: Authentication service modernization
        MEDIA: Media storage and CDN scaling
    """

    PAYMENT = 1
    ANALYTICS = 2
    AUTH = 3
    MEDIA = 4


# ==================== Model ====================


class QuestionnaireResponse(SQLModel, table=True):
    """
    Participant questionnaire response for thesis empirical evaluation.

    Each record represents one participant's response after viewing
    one AI-generated architecture proposal under one condition.

    A complete participant session generates 2-4 records:
        - Scenario 1 + Baseline condition
        - Scenario 1 + Multi-agent condition
        - (Optional) Scenario 2 + both conditions

    Thesis Mapping:
        trust_overall        → Primary outcome (RQ1 hypothesis test)
        risk_awareness       → Secondary outcome
        technical_soundness  → Secondary outcome
        balance              → Secondary outcome (RQ1 - "more balanced")
        actionability        → Secondary outcome
        completeness         → Secondary outcome
        persona_consistency  → Multi-agent only (RQ2)
        debate_value         → Multi-agent only (RQ2)

    Attributes:
        id: Primary key (UUID)
        participant_id: FK to user (participant)
        scenario_id: Which scenario (1=Payment, 2=Analytics...)
        condition: Experimental condition (baseline/multiagent)

        -- Likert Scales (1-7) --
        trust_overall: Overall trust in the proposal
        risk_awareness: How well risks are identified
        technical_soundness: Technical quality
        balance: Balance of perspectives
        actionability: How actionable the proposal is
        completeness: How complete the proposal is

        -- Open-Ended --
        strengths: What was good about this proposal
        concerns: What was missing or concerning
        trust_reasoning: Why they rated trust as they did

        -- Multi-Agent Only --
        persona_consistency: Did personas stay in character?
        debate_value: Did the debate add value?

        -- Metadata --
        time_to_complete_seconds: How long questionnaire took
        submitted_at: Submission timestamp
    """

    __tablename__ = "questionnaire_responses"

    # ==================== Primary Key ====================

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Response ID",
    )

    # ==================== Participant & Context ====================

    participant_id: int = Field(
        foreign_key="participants.id",  # References participants table, not users
        index=True,
        nullable=False,
        description="Participant ID (participants.id, not users.id)",
    )

    scenario_id: int = Field(
        nullable=False,
        index=True,
        description="Scenario ID (1=Payment, 2=Analytics, 3=Auth, 4=Media)",
    )

    condition: ExperimentCondition = Field(
        nullable=False,
        index=True,
        description="Experimental condition (baseline/multiagent)",
    )

    # ==================== Likert Scale Responses (1-7) ====================
    # Chapter 3: Trust Questionnaire

    trust_overall: int = Field(
        nullable=False,
        ge=1,
        le=7,
        description="Overall trust in the proposal (1=No trust, 7=Full trust)",
    )

    risk_awareness: int = Field(
        nullable=False,
        ge=1,
        le=7,
        description="How well risks are identified (1=Poor, 7=Excellent)",
    )

    technical_soundness: int = Field(
        nullable=False,
        ge=1,
        le=7,
        description="Technical quality and accuracy (1=Poor, 7=Excellent)",
    )

    balance: int = Field(
        nullable=False,
        ge=1,
        le=7,
        description="Balance of perspectives presented (1=One-sided, 7=Well-balanced)",
    )

    actionability: int = Field(
        nullable=False,
        ge=1,
        le=7,
        description="How actionable the proposal is (1=Not actionable, 7=Fully actionable)",
    )

    completeness: int = Field(
        nullable=False,
        ge=1,
        le=7,
        description="How complete the proposal is (1=Very incomplete, 7=Very complete)",
    )

    # ==================== Open-Ended Responses ====================

    strengths: str = Field(
        sa_column=Column(Text, nullable=False),
        description="What was good about this proposal?",
    )

    concerns: str = Field(
        sa_column=Column(Text, nullable=False),
        description="What was missing or concerning?",
    )

    trust_reasoning: str = Field(
        sa_column=Column(Text, nullable=False),
        description="Why did you give this trust rating?",
    )

    # ==================== Multi-Agent Only ====================
    # Only collected when condition == MULTIAGENT

    persona_consistency: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="Did the AI personas stay in character? (multi-agent only)",
    )

    debate_value: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="Did the debate add value to the proposal? (multi-agent only)",
    )

    most_convincing_persona: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Which persona was most convincing? (multi-agent only)",
    )

    # ==================== Completion Metadata ====================

    time_to_complete_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="Time spent completing questionnaire (seconds)",
    )

    order_in_session: Optional[int] = Field(
        default=None,
        ge=1,
        description="Which questionnaire this was in session (1=first, 2=second)",
    )

    session_id: Optional[str] = Field(
        default=None,
        max_length=100,
        index=True,
        description="Session ID linking related questionnaires",
    )

    condition_order: Optional[str] = Field(
        default=None,
        max_length=20,
        description=(
            "Participant's counterbalanced condition order "
            "(baseline_first / multiagent_first). "
            "Required covariate for order-effect analysis in SPSS/R."
        ),
    )

    # ==================== Data Quality Flags ====================

    is_valid: bool = Field(
        default=True,
        description="Flagged False if response seems invalid (e.g., all same values)",
    )

    quality_note: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Researcher note about response quality",
    )

    # ==================== Timestamps ====================

    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
        description="Submission timestamp (UTC)",
    )

    # ==================== Indexes ====================

    __table_args__ = (
        Index("idx_response_participant_condition", "participant_id", "condition"),
        Index("idx_response_scenario_condition", "scenario_id", "condition"),
        Index("idx_response_submitted", "submitted_at"),
        Index("idx_response_session", "session_id"),
    )

    # ==================== Helper Methods ====================

    @property
    def is_multiagent(self) -> bool:
        """Check if this response is for the multi-agent condition."""
        return self.condition == ExperimentCondition.MULTIAGENT

    @property
    def is_baseline(self) -> bool:
        """Check if this response is for the baseline condition."""
        return self.condition == ExperimentCondition.BASELINE

    @property
    def likert_scores(self) -> dict:
        """
        Get all Likert scores as a dictionary.

        Used for statistical analysis and export.

        Returns:
            dict: All Likert scores keyed by variable name
        """
        return {
            "trust_overall": self.trust_overall,
            "risk_awareness": self.risk_awareness,
            "technical_soundness": self.technical_soundness,
            "balance": self.balance,
            "actionability": self.actionability,
            "completeness": self.completeness,
        }

    @property
    def mean_score(self) -> float:
        """
        Calculate mean across all Likert items.

        Used as composite trust score for RQ1 analysis.

        Returns:
            float: Mean Likert score (1.0-7.0)
        """
        scores = list(self.likert_scores.values())
        return sum(scores) / len(scores)

    @property
    def time_to_complete_minutes(self) -> Optional[float]:
        """Get completion time in minutes."""
        if self.time_to_complete_seconds is None:
            return None
        return self.time_to_complete_seconds / 60.0

    @property
    def has_open_ended_responses(self) -> bool:
        """Check if all open-ended questions were answered."""
        return all(
            [
                self.strengths.strip(),
                self.concerns.strip(),
                self.trust_reasoning.strip(),
            ]
        )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<QuestionnaireResponse("
            f"participant={self.participant_id}, "
            f"scenario={self.scenario_id}, "
            f"condition={self.condition.value}, "
            f"trust={self.trust_overall}"
            f")>"
        )
