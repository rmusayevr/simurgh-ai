"""
Persona coding schemas for thesis RQ2 manual validation.

These schemas serve the manual coding endpoints used by the researcher
to validate AI persona consistency in debate sessions.

Methodology (Chapter 3):
    - Randomly sample 20% of debate turns
    - Manually code each turn for persona consistency
    - Calculate inter-rater reliability if multiple coders
    - Results feed RQ2: "Do AI personas maintain consistent character?"

Thesis Mapping:
    PersonaCodingCreate      → POST /persona-coding/ (submit coding record)
    PersonaCodingUpdate      → PATCH /persona-coding/{id} (correct a coding)
    PersonaCodingRead        → GET  /persona-coding/{id} (retrieve single record)
    PersonaCodingListRead    → GET  /persona-coding/ (filtered list)
    PersonaCodingExportRow   → GET  /persona-coding/export (CSV/SPSS export)
    PersonaCodingSummary     → GET  /persona-coding/summary/{debate_id} (RQ2 report)
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, model_validator

from app.models.persona_coding import InCharacterRating, HallucinationRating


# ==================== Persona Coding Create ====================


class PersonaCodingCreate(BaseModel):
    """
    Schema for submitting a manual coding record for one debate turn.

    The researcher reviews the actual debate turn text and rates it
    across four dimensions: in_character, quality_attributes,
    hallucination, and bias_alignment.

    Note:
        debate_id + turn_index + coder_id must be unique —
        one coder can only submit one coding per turn.
    """

    # ==================== Debate Context ====================

    debate_id: UUID = Field(
        description="Debate session being coded",
    )

    turn_index: int = Field(
        ge=0,
        description="0-indexed turn number within the debate session",
    )

    persona: str = Field(
        max_length=50,
        description="Persona being coded (legacy_keeper / innovator / mediator)",
    )

    # ==================== RQ2 Coding Variables ====================

    in_character: InCharacterRating = Field(
        description="Persona consistency rating (yes / partial / no)",
    )

    quality_attributes: List[str] = Field(
        default_factory=list,
        description="Quality attributes mentioned in this turn (e.g., 'reliability', 'scalability')",
    )

    hallucination: HallucinationRating = Field(
        default=HallucinationRating.NONE,
        description="Hallucination severity detected in this turn (no / minor / major)",
    )

    bias_alignment: bool = Field(
        default=True,
        description="Whether response aligns with persona's expected decision bias",
    )

    # ==================== Qualitative Evidence ====================

    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Coder's qualitative observations about this turn",
    )

    evidence_quote: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Direct quote from turn supporting the coding decision",
    )

    # ==================== Metadata ====================

    coder_id: int = Field(
        description="User ID of the researcher performing this coding",
    )

    coding_duration_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="Time spent coding this turn in seconds (research transparency)",
    )

    # ==================== Validators ====================

    @model_validator(mode="after")
    def validate_persona_name(self) -> "PersonaCodingCreate":
        """Ensure persona is one of the three known agents."""
        valid_personas = {"legacy_keeper", "innovator", "mediator"}
        if self.persona.lower() not in valid_personas:
            raise ValueError(f"persona must be one of: {', '.join(valid_personas)}")
        self.persona = self.persona.lower()
        return self

    @model_validator(mode="after")
    def validate_major_hallucination_has_note(self) -> "PersonaCodingCreate":
        """
        Major hallucinations must be documented with a note or evidence quote.
        Ensures coding decisions are traceable for thesis defense.
        """
        if self.hallucination == HallucinationRating.MAJOR:
            if not self.notes and not self.evidence_quote:
                raise ValueError(
                    "Major hallucination rating requires either notes or "
                    "evidence_quote to document the fabrication"
                )
        return self


# ==================== Persona Coding Update ====================


class PersonaCodingUpdate(BaseModel):
    """
    Schema for correcting an existing coding record.
    All fields optional — only provided fields are updated.

    Use case: researcher revisits a coding decision after
    inter-rater discussion or second review.
    """

    in_character: Optional[InCharacterRating] = None
    quality_attributes: Optional[List[str]] = None
    hallucination: Optional[HallucinationRating] = None
    bias_alignment: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    evidence_quote: Optional[str] = Field(default=None, max_length=1000)
    coding_duration_seconds: Optional[int] = Field(default=None, ge=0)


# ==================== Persona Coding Read ====================


class PersonaCodingListRead(BaseModel):
    """
    Lightweight coding record for list views and sampling overview.
    Excludes qualitative notes to keep payload small.
    """

    id: UUID
    debate_id: UUID
    turn_index: int
    persona: str
    in_character: InCharacterRating
    hallucination: HallucinationRating
    bias_alignment: bool
    quality_attribute_count: int
    coder_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @property
    def consistency_score(self) -> float:
        """Numeric score: 1.0 (yes) / 0.5 (partial) / 0.0 (no)."""
        return self.in_character.consistency_score

    @property
    def hallucination_score(self) -> float:
        """Numeric score: 0.0 (none) / 0.5 (minor) / 1.0 (major)."""
        return self.hallucination.severity_score

    @property
    def is_fully_consistent(self) -> bool:
        return self.in_character == InCharacterRating.YES

    @property
    def has_hallucination(self) -> bool:
        return self.hallucination != HallucinationRating.NONE


class PersonaCodingRead(BaseModel):
    """
    Full coding record including qualitative notes and evidence.
    Used for individual record review and inter-rater reliability checks.
    """

    id: UUID
    debate_id: UUID
    turn_index: int
    persona: str

    # RQ2 Coding Variables
    in_character: InCharacterRating
    quality_attributes: List[str]
    hallucination: HallucinationRating
    bias_alignment: bool

    # Qualitative Evidence
    notes: Optional[str]
    evidence_quote: Optional[str]

    # Metadata
    coder_id: int
    coding_duration_seconds: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @property
    def consistency_score(self) -> float:
        return self.in_character.consistency_score

    @property
    def hallucination_score(self) -> float:
        return self.hallucination.severity_score

    @property
    def is_fully_consistent(self) -> bool:
        return self.in_character == InCharacterRating.YES

    @property
    def has_hallucination(self) -> bool:
        return self.hallucination != HallucinationRating.NONE

    @property
    def quality_attribute_count(self) -> int:
        return len(self.quality_attributes)


# ==================== Export Schemas ====================


class PersonaCodingExportRow(BaseModel):
    """
    Flat export row for statistical analysis in SPSS/R.
    Used for CSV export consumed by thesis Chapter 5 RQ2 analysis.
    Numeric scores replace enums for direct statistical computation.
    """

    debate_id: str  # UUID as string for CSV compatibility
    turn_index: int
    persona: str
    in_character: str  # "yes" / "partial" / "no" as plain string
    consistency_score: float  # 1.0 / 0.5 / 0.0
    hallucination: str  # "no" / "minor" / "major" as plain string
    hallucination_score: float  # 0.0 / 0.5 / 1.0
    bias_alignment: bool
    quality_attribute_count: int
    coder_id: int
    coding_duration_seconds: Optional[int]
    created_at: str  # ISO string for CSV compatibility

    model_config = ConfigDict(from_attributes=True)


# ==================== RQ2 Summary Schemas ====================


class PersonaConsistencyBreakdown(BaseModel):
    """
    Consistency statistics for a single persona across all coded turns.
    One instance per persona (legacy_keeper, innovator, mediator).
    """

    persona: str
    total_turns_coded: int
    fully_consistent: int  # in_character == YES
    partially_consistent: int  # in_character == PARTIAL
    inconsistent: int  # in_character == NO
    mean_consistency_score: float  # average of 1.0/0.5/0.0 scores
    hallucination_count: int  # turns with MINOR or MAJOR
    major_hallucination_count: int
    bias_aligned_count: int
    top_quality_attributes: List[str] = Field(
        default_factory=list,
        description="Most frequently mentioned quality attributes for this persona",
    )

    @property
    def consistency_rate(self) -> float:
        """
        Percentage of fully + partially consistent turns.
        Primary RQ2 metric per persona.
        """
        if self.total_turns_coded == 0:
            return 0.0
        return round(
            (self.fully_consistent + self.partially_consistent)
            / self.total_turns_coded,
            3,
        )

    @property
    def hallucination_rate(self) -> float:
        """Percentage of turns with any hallucination detected."""
        if self.total_turns_coded == 0:
            return 0.0
        return round(self.hallucination_count / self.total_turns_coded, 3)


class PersonaCodingSummary(BaseModel):
    """
    Full RQ2 summary for a debate session's manual coding.

    Aggregates all PersonaCoding records for one DebateSession
    into the metrics needed for thesis Chapter 5.

    Maps to DebatePersonaConsistencyUpdate for writing scores
    back to the DebateSession record.
    """

    debate_id: UUID
    total_turns_in_debate: int
    turns_coded: int  # should be ~20% of total
    coding_coverage: float  # turns_coded / total_turns_in_debate

    # Per-persona breakdowns
    legacy_keeper: PersonaConsistencyBreakdown
    innovator: PersonaConsistencyBreakdown
    mediator: PersonaConsistencyBreakdown

    # Overall metrics
    overall_consistency_rate: float
    overall_hallucination_rate: float
    overall_bias_alignment_rate: float

    # Coder metadata
    coder_ids: List[int] = Field(
        description="All coders who contributed to this debate's coding",
    )
    total_coding_time_seconds: Optional[int]

    @property
    def meets_sampling_threshold(self) -> bool:
        """Check if at least 20% of turns have been coded (thesis requirement)."""
        return self.coding_coverage >= 0.20

    @property
    def total_coding_time_minutes(self) -> Optional[float]:
        if self.total_coding_time_seconds is None:
            return None
        return round(self.total_coding_time_seconds / 60.0, 2)

    @property
    def to_consistency_update(self) -> dict:
        """
        Export scores in the format expected by DebatePersonaConsistencyUpdate.
        Used to write RQ2 results back to the DebateSession record.
        """
        return {
            "legacy_keeper_consistency": self.legacy_keeper.mean_consistency_score,
            "innovator_consistency": self.innovator.mean_consistency_score,
            "mediator_consistency": self.mediator.mean_consistency_score,
        }
