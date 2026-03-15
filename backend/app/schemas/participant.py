"""
Participant schemas for thesis user study registration.

Covers:
    - ParticipantCreate: POST /experiment/register (consent + demographics)
    - ParticipantRead:   GET  /experiment/participant/{id}
    - ParticipantUpdate: PATCH used internally to mark completion

Validation rules enforce the ethics requirements:
    - consent_given must be True (reject registration otherwise)
    - years_experience must be non-negative
    - familiarity_with_ai must be a valid 1–7 Likert value
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.participant import ExperienceLevel, ConditionOrder


# ==================== Create (Registration) ====================


class ParticipantCreate(BaseModel):
    """
    Schema for participant registration form submission.

    Submitted via POST /experiment/register after the user
    completes the consent and demographics form.

    Validation ensures:
        - All three consent checkboxes were ticked (consent_given == True)
        - Experience data is plausible
        - AI familiarity is a valid Likert value
    """

    experience_level: ExperienceLevel = Field(
        description="Self-reported experience level",
    )

    years_experience: int = Field(
        ge=0,
        le=50,
        description="Years of software development experience",
    )

    familiarity_with_ai: int = Field(
        ge=1,
        le=7,
        description="AI tool familiarity (1=Never used, 7=Use daily)",
    )

    consent_given: bool = Field(
        description="Must be True — participant ticked all consent checkboxes",
    )

    @model_validator(mode="after")
    def validate_consent(self) -> "ParticipantCreate":
        """Reject registration if consent was not explicitly given."""
        if not self.consent_given:
            raise ValueError(
                "Registration requires explicit consent. "
                "All consent checkboxes must be ticked."
            )
        return self


# ==================== Read ====================


class ParticipantRead(BaseModel):
    """
    Schema returned after successful registration or on GET.

    Includes the randomly assigned condition_order so the frontend
    can determine which condition to show first.
    """

    id: int
    user_id: int
    experience_level: ExperienceLevel
    years_experience: int
    familiarity_with_ai: int
    consent_given: bool
    consent_timestamp: Optional[datetime]
    assigned_condition_order: ConditionOrder
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    @property
    def condition_sequence(self) -> list[str]:
        """Ordered list of conditions: ['baseline', 'multiagent'] or reversed."""
        if self.assigned_condition_order == ConditionOrder.BASELINE_FIRST:
            return ["baseline", "multiagent"]
        return ["multiagent", "baseline"]


# ==================== Internal Update ====================


class ParticipantComplete(BaseModel):
    """Used internally to mark a participant as having finished the experiment."""

    completed_at: datetime = Field(
        description="UTC timestamp when exit survey was submitted",
    )
