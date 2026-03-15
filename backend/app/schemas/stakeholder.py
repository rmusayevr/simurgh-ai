from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import Optional
from datetime import datetime

from app.models.stakeholder import InfluenceLevel, InterestLevel, Sentiment


# ==================== Stakeholder Schemas ====================


class StakeholderCreate(BaseModel):
    """Schema for creating a new AI-analyzed stakeholder."""

    name: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    department: Optional[str] = Field(default=None, max_length=200)
    email: Optional[EmailStr] = Field(
        default=None,
        description="Contact email for approval notifications",
    )
    influence: InfluenceLevel = InfluenceLevel.MEDIUM
    interest: InterestLevel = InterestLevel.MEDIUM
    sentiment: Sentiment = Sentiment.NEUTRAL
    notes: Optional[str] = None
    concerns: Optional[str] = Field(
        default=None,
        description="Key concerns that need to be addressed",
    )
    motivations: Optional[str] = Field(
        default=None,
        description="What motivates this stakeholder",
    )
    approval_role: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Role in approval workflow (e.g., 'cto', 'tech_lead')",
    )
    notify_on_approval_needed: bool = Field(
        default=True,
        description="Send email when assigned as gate approver",
    )


class StakeholderUpdate(BaseModel):
    """
    Schema for updating a stakeholder.
    All fields optional — only provided fields are updated.
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    role: Optional[str] = Field(default=None, min_length=1, max_length=200)
    department: Optional[str] = Field(default=None, max_length=200)
    email: Optional[EmailStr] = None
    influence: Optional[InfluenceLevel] = None
    interest: Optional[InterestLevel] = None
    sentiment: Optional[Sentiment] = None
    notes: Optional[str] = None
    concerns: Optional[str] = None
    motivations: Optional[str] = None
    approval_role: Optional[str] = Field(default=None, max_length=100)
    notify_on_approval_needed: Optional[bool] = None


class StakeholderListRead(BaseModel):
    """
    Lightweight stakeholder summary for list and dashboard views.
    Excludes heavy AI-generated fields (strategic_plan, concerns, motivations).
    Exposes computed risk properties needed for the Political Risk Heatmap.
    """

    id: int
    name: str
    role: str
    department: Optional[str]
    email: Optional[str]
    influence: InfluenceLevel
    interest: InterestLevel
    sentiment: Sentiment
    approval_role: Optional[str]
    notify_on_approval_needed: bool
    project_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @property
    def power_interest_quadrant(self) -> str:
        """Mendelow's Matrix quadrant — used by frontend heatmap."""
        high_influence = self.influence == InfluenceLevel.HIGH
        high_interest = self.interest == InterestLevel.HIGH
        if high_influence and high_interest:
            return "Manage Closely"
        elif high_influence and not high_interest:
            return "Keep Satisfied"
        elif not high_influence and high_interest:
            return "Keep Informed"
        else:
            return "Monitor"

    @property
    def risk_level(self) -> str:
        """Risk level based on influence weight × sentiment risk score."""
        scores = {
            Sentiment.CHAMPION: 0,
            Sentiment.SUPPORTIVE: 1,
            Sentiment.NEUTRAL: 2,
            Sentiment.CONCERNED: 3,
            Sentiment.RESISTANT: 4,
            Sentiment.BLOCKER: 5,
        }
        weights = {
            InfluenceLevel.HIGH: 3,
            InfluenceLevel.MEDIUM: 2,
            InfluenceLevel.LOW: 1,
        }
        risk_score = scores[self.sentiment] * weights[self.influence]
        if risk_score >= 12:
            return "Critical"
        elif risk_score >= 8:
            return "High"
        elif risk_score >= 4:
            return "Medium"
        else:
            return "Low"

    @property
    def needs_attention(self) -> bool:
        """High influence + negative sentiment, or blocker regardless of influence."""
        negative = self.sentiment in (Sentiment.RESISTANT, Sentiment.BLOCKER)
        return (
            negative and self.influence == InfluenceLevel.HIGH
        ) or self.sentiment == Sentiment.BLOCKER


class StakeholderRead(BaseModel):
    """
    Full stakeholder detail including AI-generated strategic plan.
    Used for individual stakeholder detail view.
    """

    id: int
    name: str
    role: str
    department: Optional[str]
    email: Optional[str]
    influence: InfluenceLevel
    interest: InterestLevel
    sentiment: Sentiment
    notes: Optional[str]
    strategic_plan: Optional[str]
    concerns: Optional[str]
    motivations: Optional[str]
    approval_role: Optional[str]
    notify_on_approval_needed: bool
    project_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @property
    def power_interest_quadrant(self) -> str:
        high_influence = self.influence == InfluenceLevel.HIGH
        high_interest = self.interest == InterestLevel.HIGH
        if high_influence and high_interest:
            return "Manage Closely"
        elif high_influence and not high_interest:
            return "Keep Satisfied"
        elif not high_influence and high_interest:
            return "Keep Informed"
        else:
            return "Monitor"

    @property
    def risk_level(self) -> str:
        scores = {
            Sentiment.CHAMPION: 0,
            Sentiment.SUPPORTIVE: 1,
            Sentiment.NEUTRAL: 2,
            Sentiment.CONCERNED: 3,
            Sentiment.RESISTANT: 4,
            Sentiment.BLOCKER: 5,
        }
        weights = {
            InfluenceLevel.HIGH: 3,
            InfluenceLevel.MEDIUM: 2,
            InfluenceLevel.LOW: 1,
        }
        risk_score = scores[self.sentiment] * weights[self.influence]
        if risk_score >= 12:
            return "Critical"
        elif risk_score >= 8:
            return "High"
        elif risk_score >= 4:
            return "Medium"
        else:
            return "Low"

    @property
    def needs_attention(self) -> bool:
        negative = self.sentiment in (Sentiment.RESISTANT, Sentiment.BLOCKER)
        return (
            negative and self.influence == InfluenceLevel.HIGH
        ) or self.sentiment == Sentiment.BLOCKER


class StakeholderMatrix(BaseModel):
    key_players: list[StakeholderRead]
    keep_satisfied: list[StakeholderRead]
    keep_informed: list[StakeholderRead]
    monitor: list[StakeholderRead]
