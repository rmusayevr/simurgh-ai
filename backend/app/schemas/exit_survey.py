"""
Exit survey schemas for thesis participant preference capture.

Used in Chapter 5 Section 5.3.3 ("Participant Preferences").
Collected once per participant after both experimental conditions are complete.

Critical: preferred_system labels ("first" / "second") do NOT reveal which
condition was baseline vs multi-agent. The debrief text mapping is rendered
only on the frontend AFTER the response is submitted.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.models.exit_survey import PreferredSystem, FatigueLevel


# ==================== Exit Survey Create ====================


class ExitSurveyCreate(BaseModel):
    """
    Schema for submitting the post-experiment exit survey.

    Submitted once per participant immediately after the second
    TrustQuestionnaire is completed.

    Validation:
        - preference_reasoning required and must be non-empty
        - interface_rating must be 1–7
        - preferred_system and experienced_fatigue are enum-validated
    """

    participant_id: int = Field(
        description="Participant ID (FK to participants.id)",
    )

    preferred_system: PreferredSystem = Field(
        description="Preferred AI system: first / second / no_preference / not_sure",
    )

    preferred_system_actual: Optional[str] = Field(
        default=None,
        max_length=20,
        description=(
            "Resolved preferred system sent from frontend: 'baseline', 'multiagent', "
            "'no_preference', or 'not_sure'. Frontend resolves this using the participant's "
            "assigned_condition_order before submission."
        ),
    )

    preference_reasoning: str = Field(
        min_length=1,
        max_length=5000,
        description="Open-ended explanation of system preference",
    )

    interface_rating: int = Field(
        ge=1,
        le=7,
        description="Overall interface experience rating (1=Very Poor, 7=Excellent)",
    )

    experienced_fatigue: FatigueLevel = Field(
        description="Self-reported fatigue level (none / a_little / yes_significantly)",
    )

    technical_issues: Optional[str] = Field(
        default=None,
        max_length=3000,
        description="Optional: description of any technical problems",
    )

    additional_feedback: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Optional: any other comments",
    )

    @field_validator("preference_reasoning")
    @classmethod
    def reasoning_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("preference_reasoning must not be blank")
        return v.strip()


# ==================== Exit Survey Read ====================


class ExitSurveyRead(BaseModel):
    """
    Schema returned after exit survey submission or on researcher retrieval.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    participant_id: int
    preferred_system: PreferredSystem
    preferred_system_actual: Optional[str] = None
    preference_reasoning: str
    interface_rating: int
    experienced_fatigue: FatigueLevel
    technical_issues: Optional[str] = None
    additional_feedback: Optional[str] = None
    submitted_at: datetime


# ==================== Exit Survey Export ====================


class ExitSurveyExportRow(BaseModel):
    """
    Flat row for CSV/SPSS export. Used in thesis Chapter 5 data export.
    """

    model_config = ConfigDict(from_attributes=True)

    participant_id: int
    preferred_system: str
    preferred_system_actual: Optional[str] = None
    preference_reasoning: str
    interface_rating: int
    experienced_fatigue: str
    has_technical_issues: bool
    submitted_at: str
