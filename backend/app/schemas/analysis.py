from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional

from app.models.stakeholder import Sentiment, InfluenceLevel, InterestLevel


# ==================== Strategy Request ====================


class StrategyRequest(BaseModel):
    """
    Request schema for generating an AI stakeholder communication strategy.

    The service uses this to pull relevant RAG context from project documents
    and the proposal PRD to generate a targeted engagement plan.
    """

    stakeholder_id: int
    proposal_id: Optional[int] = Field(
        default=None,
        description="Contextualize strategy to a specific proposal (recommended)",
    )
    force_regenerate: bool = Field(
        default=False,
        description="Bypass cache and regenerate even if strategic_plan exists",
    )


# ==================== Strategy Response ====================


class StrategyResponse(BaseModel):
    """
    AI-generated communication strategy for a stakeholder.

    Returned by the strategy generation endpoint and cached
    in Stakeholder.strategic_plan as Markdown.
    """

    stakeholder_id: int
    stakeholder_name: str
    role: str

    # Context from Stakeholder model
    sentiment: Sentiment
    influence: InfluenceLevel
    interest: InterestLevel
    power_interest_quadrant: str  # "Manage Closely" / "Keep Satisfied" / etc.
    risk_level: str  # "Critical" / "High" / "Medium" / "Low"

    # AI-generated content
    recommended_approach: str = Field(
        description="High-level engagement strategy tailored to quadrant and sentiment",
    )
    key_talking_points: List[str] = Field(
        min_length=1,
        max_length=10,
        description="Specific arguments to use with this stakeholder",
    )
    concerns_to_address: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Stakeholder concerns that must be acknowledged",
    )
    sample_outreach: str = Field(
        description="Draft message or email opener for initial contact",
    )

    # Cache metadata
    was_cached: bool = Field(
        default=False,
        description="Whether this response was served from cache (Stakeholder.strategic_plan)",
    )
    generated_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp of when strategy was generated",
    )

    model_config = ConfigDict(from_attributes=False)


# ==================== Cache Status ====================


class StrategyCacheStatus(BaseModel):
    """
    Cache status for a stakeholder's strategic plan.
    Lets the frontend show 'Generate' vs 'Regenerate' button state.
    """

    stakeholder_id: int
    has_cached_plan: bool
    stakeholder_name: str
    sentiment: Sentiment
    risk_level: str
