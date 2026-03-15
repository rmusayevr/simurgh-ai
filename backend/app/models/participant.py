"""
Participant model for thesis user study.

Stores research participant registration, demographics, and consent
for the A/B experiment evaluating the Council of Agents framework.

Research Context:
    Each Participant maps to one authenticated User and represents
    a single research subject in the controlled user study.
    N = 5–10 participants per thesis Section 3.3.

Consent & Ethics:
    consent_given must be True before any experiment data is collected.
    consent_timestamp records when consent was given for IRB documentation.

Counterbalancing:
    assigned_condition_order ensures ~50% baseline-first, ~50% multiagent-first
    to control for order effects in the within-subject A/B design.
"""

import random
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import Index


# ==================== Enums ====================


class ExperienceLevel(str, Enum):
    """
    Participant's professional experience level.

    Used as a covariate in Chapter 5 demographic reporting.
    """

    MSC_STUDENT = "msc_student"
    JUNIOR = "junior"
    SENIOR = "senior"
    ARCHITECT = "architect"

    @property
    def display_name(self) -> str:
        return {
            ExperienceLevel.MSC_STUDENT: "MSc Student",
            ExperienceLevel.JUNIOR: "Junior Developer (0–2 years)",
            ExperienceLevel.SENIOR: "Senior Developer (3–7 years)",
            ExperienceLevel.ARCHITECT: "Software Architect (8+ years)",
        }[self]


class ConditionOrder(str, Enum):
    """
    Counterbalancing order for A/B conditions.

    BASELINE_FIRST: Participant sees single-agent first, multi-agent second.
    MULTIAGENT_FIRST: Participant sees multi-agent first, single-agent second.

    Randomly assigned 50/50 at registration to control for order effects.
    """

    BASELINE_FIRST = "baseline_first"
    MULTIAGENT_FIRST = "multiagent_first"

    @classmethod
    def random(cls) -> "ConditionOrder":
        """Randomly assign condition order (50/50 split)."""
        return random.choice([cls.BASELINE_FIRST, cls.MULTIAGENT_FIRST])


# ==================== Model ====================


class Participant(SQLModel, table=True):
    """
    Research participant registration record.

    One record per user study participant. Created during the
    registration/consent step before the experiment begins.

    Lifecycle:
        1. User completes consent + demographics → Participant created
        2. Participant completes both scenarios → completed_at set
        3. Data exported via /thesis/export/thesis-data for Chapter 5

    Thesis Usage:
        - Demographics reported in Chapter 5 Section 5.1
        - condition_order used to verify counterbalancing worked
        - consent_given provides IRB documentation

    Attributes:
        id: Primary key (integer, consistent with users.id pattern)
        user_id: FK to users table (the authenticated account)
        experience_level: Self-reported seniority level
        years_experience: Self-reported years in software development
        familiarity_with_ai: Likert 1–7, AI tool familiarity (TAM baseline)
        consent_given: Must be True; recorded at registration
        consent_timestamp: UTC timestamp of consent for IRB records
        assigned_condition_order: Counterbalanced A/B order (random at registration)
        created_at: Registration timestamp
        completed_at: Set when exit survey is submitted (nullable until then)
    """

    __tablename__ = "participants"

    # ==================== Primary Key ====================

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Participant ID (auto-increment)",
    )

    # ==================== User Link ====================

    user_id: int = Field(
        foreign_key="users.id",
        unique=True,  # One participant record per user account
        nullable=False,
        index=True,
        description="FK to authenticated user account",
    )

    # ==================== Demographics ====================

    experience_level: ExperienceLevel = Field(
        nullable=False,
        description="Self-reported experience level (msc_student/junior/senior/architect)",
    )

    years_experience: int = Field(
        nullable=False,
        ge=0,
        le=50,
        description="Years of software development experience",
    )

    familiarity_with_ai: int = Field(
        nullable=False,
        ge=1,
        le=7,
        description="AI tool familiarity Likert 1–7 (TAM Technology Acceptance baseline)",
    )

    # ==================== Consent ====================

    consent_given: bool = Field(
        default=False,
        nullable=False,
        description="Must be True — participant explicitly agreed to all consent items",
    )

    consent_timestamp: Optional[datetime] = Field(
        default=None,
        nullable=True,
        description="UTC timestamp when consent was given (IRB documentation)",
    )

    # ==================== Experiment Assignment ====================

    assigned_condition_order: ConditionOrder = Field(
        nullable=False,
        description="Counterbalanced condition order (baseline_first / multiagent_first)",
    )

    # ==================== Timestamps ====================

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
        description="Registration timestamp (UTC)",
    )

    completed_at: Optional[datetime] = Field(
        default=None,
        nullable=True,
        description="Experiment completion timestamp — None until exit survey submitted",
    )

    # ==================== Indexes ====================

    __table_args__ = (
        Index("idx_participant_user", "user_id"),
        Index("idx_participant_condition_order", "assigned_condition_order"),
        Index("idx_participant_created", "created_at"),
    )

    # ==================== Properties ====================

    @property
    def is_completed(self) -> bool:
        """Check if participant has finished the full experiment."""
        return self.completed_at is not None

    def __repr__(self) -> str:
        return (
            f"<Participant("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"level={self.experience_level.value}, "
            f"order={self.assigned_condition_order.value}, "
            f"completed={self.is_completed}"
            f")>"
        )
