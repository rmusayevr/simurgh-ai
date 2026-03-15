"""
Questionnaire schemas for thesis empirical evaluation.

These schemas serve the data collection endpoints for RQ1 and RQ3 evaluation.
Each QuestionnaireResponse represents one participant's rating of one
AI-generated proposal under one experimental condition (baseline vs multiagent).

Thesis Mapping:
    QuestionnaireCreate      → POST /questionnaire/ (participant submission)
    QuestionnaireRead        → GET  /questionnaire/{id} (researcher retrieval)
    QuestionnaireUpdate      → PATCH /questionnaire/{id} (flag invalid)
    QuestionnaireListRead    → GET  /questionnaire/ (filtered list)
    QuestionnaireExportRow   → GET  /questionnaire/export (CSV/SPSS export)
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from app.models.questionnaire import ExperimentCondition


# ==================== Questionnaire Create ====================


class QuestionnaireCreate(BaseModel):
    """
    Schema for submitting a questionnaire response.

    Collected immediately after a participant views an AI-generated proposal.
    Likert scales are 1-7 as defined in thesis Chapter 3.
    Multi-agent only fields (persona_consistency, debate_value,
    most_convincing_persona) are optional and only relevant when
    condition == MULTIAGENT.
    """

    # ==================== Participant & Context ====================

    participant_id: int = Field(
        description="Participant user ID",
    )

    scenario_id: int = Field(
        ge=1,
        le=4,
        description="Scenario ID (1=Payment, 2=Analytics, 3=Auth, 4=Media)",
    )

    condition: ExperimentCondition = Field(
        description="Experimental condition (baseline/multiagent)",
    )

    # ==================== Likert Scales (1-7) ====================

    trust_overall: int = Field(
        ge=1,
        le=7,
        description="Overall trust in the proposal (1=No trust, 7=Full trust)",
    )

    risk_awareness: int = Field(
        ge=1,
        le=7,
        description="How well risks are identified (1=Poor, 7=Excellent)",
    )

    technical_soundness: int = Field(
        ge=1,
        le=7,
        description="Technical quality and accuracy (1=Poor, 7=Excellent)",
    )

    balance: int = Field(
        ge=1,
        le=7,
        description="Balance of perspectives (1=One-sided, 7=Well-balanced)",
    )

    actionability: int = Field(
        ge=1,
        le=7,
        description="How actionable the proposal is (1=Not actionable, 7=Fully actionable)",
    )

    completeness: int = Field(
        ge=1,
        le=7,
        description="How complete the proposal is (1=Very incomplete, 7=Very complete)",
    )

    # ==================== Open-Ended Responses ====================

    strengths: str = Field(
        min_length=1,
        max_length=5000,
        description="What was good about this proposal?",
    )

    concerns: str = Field(
        min_length=1,
        max_length=5000,
        description="What was missing or concerning?",
    )

    trust_reasoning: str = Field(
        min_length=1,
        max_length=5000,
        description="Why did you give this trust rating?",
    )

    # ==================== Multi-Agent Only ====================

    persona_consistency: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Did the AI personas stay in character? (multiagent only)",
    )

    debate_value: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Did the debate add value to the proposal? (multiagent only)",
    )

    most_convincing_persona: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Which persona was most convincing? (multiagent only)",
    )

    # ==================== Session Metadata ====================

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
        description="Session ID linking related questionnaires from same participant",
    )

    condition_order: Optional[str] = Field(
        default=None,
        max_length=20,
        description=(
            "Participant's assigned condition order (baseline_first / multiagent_first). "
            "Must be included for counterbalancing analysis — covariate in paired t-test."
        ),
    )

    # ==================== Validators ====================

    @field_validator("strengths", "concerns", "trust_reasoning", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Ensure open-ended responses aren't just whitespace."""
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def validate_multiagent_fields(self) -> "QuestionnaireCreate":
        """
        Warn if multiagent-specific fields are submitted for baseline condition.
        These fields are only meaningful when condition == MULTIAGENT.
        """
        if self.condition == ExperimentCondition.BASELINE:
            if any(
                [
                    self.persona_consistency,
                    self.debate_value,
                    self.most_convincing_persona,
                ]
            ):
                raise ValueError(
                    "persona_consistency, debate_value, and most_convincing_persona "
                    "are only valid for the multiagent condition"
                )
        return self


# ==================== Questionnaire Read ====================


class QuestionnaireListRead(BaseModel):
    """
    Lightweight questionnaire summary for researcher list views.
    Excludes open-ended text responses to keep payload small.
    """

    id: UUID
    participant_id: int
    scenario_id: int
    condition: ExperimentCondition
    trust_overall: int
    risk_awareness: int
    technical_soundness: int
    balance: int
    actionability: int
    completeness: int
    is_valid: bool
    session_id: Optional[str]
    order_in_session: Optional[int]
    time_to_complete_seconds: Optional[int]
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @property
    def mean_score(self) -> float:
        """Composite trust score across all Likert items — primary RQ1 metric."""
        scores = [
            self.trust_overall,
            self.risk_awareness,
            self.technical_soundness,
            self.balance,
            self.actionability,
            self.completeness,
        ]
        return round(sum(scores) / len(scores), 3)

    @property
    def is_multiagent(self) -> bool:
        return self.condition == ExperimentCondition.MULTIAGENT


class QuestionnaireRead(BaseModel):
    """
    Full questionnaire response including open-ended answers.
    Used for individual response review and qualitative thematic analysis.
    """

    id: UUID
    participant_id: int
    scenario_id: int
    condition: ExperimentCondition

    # Likert Scores
    trust_overall: int
    risk_awareness: int
    technical_soundness: int
    balance: int
    actionability: int
    completeness: int

    # Open-Ended
    strengths: str
    concerns: str
    trust_reasoning: str

    # Multi-Agent Only
    persona_consistency: Optional[str]
    debate_value: Optional[str]
    most_convincing_persona: Optional[str]

    # Metadata
    time_to_complete_seconds: Optional[int]
    order_in_session: Optional[int]
    session_id: Optional[str]
    condition_order: Optional[
        str
    ]  # "baseline_first" / "multiagent_first" — order-effect covariate
    is_valid: bool
    quality_note: Optional[str]
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @property
    def mean_score(self) -> float:
        """Composite trust score — primary outcome variable for RQ1 t-test."""
        scores = [
            self.trust_overall,
            self.risk_awareness,
            self.technical_soundness,
            self.balance,
            self.actionability,
            self.completeness,
        ]
        return round(sum(scores) / len(scores), 3)

    @property
    def likert_scores(self) -> dict:
        return {
            "trust_overall": self.trust_overall,
            "risk_awareness": self.risk_awareness,
            "technical_soundness": self.technical_soundness,
            "balance": self.balance,
            "actionability": self.actionability,
            "completeness": self.completeness,
        }

    @property
    def is_multiagent(self) -> bool:
        return self.condition == ExperimentCondition.MULTIAGENT

    @property
    def time_to_complete_minutes(self) -> Optional[float]:
        if self.time_to_complete_seconds is None:
            return None
        return round(self.time_to_complete_seconds / 60.0, 2)


# ==================== Questionnaire Update ====================


class QuestionnaireUpdate(BaseModel):
    """
    Schema for updating questionnaire metadata.

    Used by researchers to flag invalid responses or update quality notes.
    Likert scores and open-ended responses cannot be updated to preserve
    data integrity.
    """

    is_valid: Optional[bool] = Field(
        default=None,
        description="Mark response as valid/invalid for analysis",
    )

    quality_note: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Researcher notes on data quality",
    )


# ==================== Data Quality ====================


class QuestionnaireInvalidate(BaseModel):
    """Schema for researcher flagging a response as invalid."""

    reason: str = Field(
        min_length=5,
        max_length=500,
        description="Why this response is being excluded from analysis",
    )


# ==================== Export Schemas ====================


class QuestionnaireExportRow(BaseModel):
    """
    Flat export row for statistical analysis in SPSS/R.

    Maps directly to the model's to_analysis_dict() output.
    Used for CSV export endpoint consumed by thesis Chapter 5 analysis.
    """

    participant_id: int
    scenario_id: int
    condition: str  # "baseline" or "multiagent" as plain string for SPSS
    condition_order: Optional[
        str
    ]  # "baseline_first" or "multiagent_first" — order effect covariate
    trust_overall: int
    risk_awareness: int
    technical_soundness: int
    balance: int
    actionability: int
    completeness: int
    mean_score: float
    time_to_complete_seconds: Optional[int]
    order_in_session: Optional[int]
    session_id: Optional[str]
    is_valid: bool
    submitted_at: str  # ISO string for CSV compatibility

    model_config = ConfigDict(from_attributes=True)


class QuestionnaireExportSummary(BaseModel):
    """
    Aggregated summary statistics for a set of responses.

    Used for the thesis RQ1 reporting endpoint — provides
    descriptive statistics split by condition for paired t-test preparation.
    """

    total_responses: int
    valid_responses: int
    baseline_count: int
    multiagent_count: int

    # Mean scores by condition
    baseline_mean_trust: float
    multiagent_mean_trust: float
    mean_difference: float  # multiagent - baseline (RQ1 primary outcome)

    # Per-item means (baseline vs multiagent)
    baseline_means: dict
    multiagent_means: dict

    # Data quality
    invalid_count: int
    straightlining_detected: int

    @property
    def effect_direction(self) -> str:
        """Whether multiagent scores higher, lower, or equal to baseline."""
        if self.mean_difference > 0:
            return "multiagent_higher"
        elif self.mean_difference < 0:
            return "baseline_higher"
        else:
            return "equal"
