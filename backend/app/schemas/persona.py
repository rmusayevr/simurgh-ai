"""
Persona schemas for runtime debate engine.

These are NOT database models - they are Pydantic schemas used
by the debate service at runtime.

PersonaProfile: Static configuration of each AI agent persona
PersonaAnalysis: Computed metrics from a persona's response (thesis RQ2)
"""

from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, Field


# ==================== Persona Configuration ====================


class PersonaProfile(BaseModel):
    """
    Static configuration for an AI debate persona.

    Defines behavior, concerns, and decision-making style
    for Legacy Keeper, Innovator, and Mediator agents.

    Note:
        system_prompt is excluded from serialization via model_config
        to prevent leaking prompt engineering IP in API responses.
    """

    key: str = Field(
        description="Unique persona identifier (e.g., 'legacy_keeper')",
    )

    name: str = Field(
        description="Display name (e.g., 'The Legacy Keeper')",
    )

    role: str = Field(
        description="Role description for context",
    )

    primary_concerns: List[str] = Field(
        default_factory=list,
        description="What this persona prioritizes in decisions",
    )

    quality_attributes: List[str] = Field(
        default_factory=list,
        description="Architecture quality attributes this persona champions",
    )

    decision_bias: str = Field(
        description="How this persona frames architectural decisions",
    )

    system_prompt: str = Field(
        exclude=True,  # never serialized in API responses
        description="Full system prompt for AI model (excluded from serialization)",
    )

    # ==================== Properties ====================

    @property
    def keyword_set(self) -> set:
        """
        Get all keywords associated with this persona.
        Internal use only — not serializable.
        """
        keywords = set()
        for attr in self.quality_attributes:
            keywords.update(attr.lower().split())
        for concern in self.primary_concerns:
            keywords.update(concern.lower().split())
        return keywords

    def calculate_consistency_score(self, response_text: str) -> float:
        """
        Calculate persona consistency score for a response.

        Uses substring matching instead of word splitting to correctly
        handle compound terms (e.g., 'performance-critical', 'fault-tolerant').

        Args:
            response_text: AI agent's response text

        Returns:
            float: Consistency score (0.0-1.0)
        """
        if not response_text or not self.keyword_set:
            return 0.0

        response_lower = response_text.lower()
        matches = sum(1 for kw in self.keyword_set if kw in response_lower)

        return min(1.0, matches / max(len(self.keyword_set), 1))

    def get_matched_keywords(self, response_text: str) -> List[str]:
        """
        Get list of persona keywords found in a response.

        Used to populate PersonaAnalysis.keyword_matches
        and PersonaCoding.quality_attributes.

        Args:
            response_text: AI agent's response text

        Returns:
            List[str]: Matched keywords
        """
        if not response_text:
            return []
        response_lower = response_text.lower()
        return [kw for kw in self.keyword_set if kw in response_lower]


# ==================== Thesis RQ2 Analysis ====================


class PersonaAnalysis(BaseModel):
    """
    Automated analysis of a persona's response for thesis RQ2.

    Computed at runtime by the debate service to supplement
    manual PersonaCoding records.
    """

    persona_type: str = Field(
        description="Persona key (e.g., 'legacy_keeper')",
    )

    response_text: str = Field(
        description="The AI response being analyzed",
    )

    quality_attributes_mentioned: List[str] = Field(
        default_factory=list,
        description="Quality attributes detected in response",
    )

    bias_alignment_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How well response aligns with persona's bias (0.0-1.0)",
    )

    consistency_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall persona consistency score (0.0-1.0)",
    )

    keyword_matches: List[str] = Field(
        default_factory=list,
        description="Specific persona keywords found in response",
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        description="When analysis was performed (UTC)",
    )
