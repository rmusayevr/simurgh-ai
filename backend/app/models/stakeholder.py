"""
Stakeholder and ProjectStakeholderLink models.

Stakeholder represents AI-analyzed personas within a project context,
mapping real-world roles and their influence on architectural decisions.

ProjectStakeholderLink is the many-to-many association between Users
and Projects with role-based permissions.

Models:
    - Stakeholder: AI-defined stakeholder persona for a project
    - ProjectStakeholderLink: User-Project membership with role

Relationships:
    Stakeholder -> Project (many stakeholders per project)
    ProjectStakeholderLink -> Project, User (junction table)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship, Column, Text, String
from sqlalchemy import Index

if TYPE_CHECKING:
    from app.models.project import Project


# ==================== Stakeholder Enums ====================


class InfluenceLevel(str, Enum):
    """
    Stakeholder's organizational influence level.

    Used in power/interest grid analysis (Mendelow's Matrix).

    Levels:
        HIGH: Executive/decision-maker (CTO, CEO, VP Engineering)
        MEDIUM: Senior contributor (Tech Lead, Product Manager)
        LOW: Contributor (Developer, Designer)
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    @property
    def weight(self) -> int:
        """Numeric weight for calculations."""
        return {"HIGH": 3, "MEDIUM": 2, "LOW": 1}[self.value]


class InterestLevel(str, Enum):
    """
    Stakeholder's interest in the project outcome.

    Combined with InfluenceLevel to determine engagement strategy.

    Levels:
        HIGH: Directly impacted by outcome
        MEDIUM: Indirectly affected
        LOW: Minimal stake in outcome
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    @property
    def weight(self) -> int:
        """Numeric weight for calculations."""
        return {"HIGH": 3, "MEDIUM": 2, "LOW": 1}[self.value]


class Sentiment(str, Enum):
    """
    Stakeholder's attitude toward the project/proposal.

    Ordered from most supportive to most resistant.
    Used to determine communication and engagement strategy.

    Values:
        CHAMPION: Actively advocating and helping
        SUPPORTIVE: Positive, will vote yes
        NEUTRAL: Indifferent, needs engagement
        CONCERNED: Has questions/doubts
        RESISTANT: Actively opposing
        BLOCKER: Will veto/kill project if not addressed
    """

    CHAMPION = "CHAMPION"
    SUPPORTIVE = "SUPPORTIVE"
    NEUTRAL = "NEUTRAL"
    CONCERNED = "CONCERNED"
    RESISTANT = "RESISTANT"
    BLOCKER = "BLOCKER"

    @property
    def is_positive(self) -> bool:
        """Check if sentiment is positive."""
        return self in (Sentiment.CHAMPION, Sentiment.SUPPORTIVE)

    @property
    def is_negative(self) -> bool:
        """Check if sentiment is negative or blocking."""
        return self in (Sentiment.RESISTANT, Sentiment.BLOCKER)

    @property
    def risk_score(self) -> int:
        """
        Numeric risk score for this sentiment.

        Higher = more risk to project.
        """
        scores = {
            Sentiment.CHAMPION: 0,
            Sentiment.SUPPORTIVE: 1,
            Sentiment.NEUTRAL: 2,
            Sentiment.CONCERNED: 3,
            Sentiment.RESISTANT: 4,
            Sentiment.BLOCKER: 5,
        }
        return scores[self]


# ==================== Stakeholder Model ====================


class Stakeholder(SQLModel, table=True):
    """
    AI-analyzed stakeholder persona for a project.

    Represents a person or role that influences architectural decisions.
    Used by AI agents to generate targeted communication plans
    and identify potential blockers.

    Attributes:
        id: Primary key
        name: Stakeholder name
        role: Job title/role
        department: Organizational department
        email: Contact email
        influence: Organizational influence level
        interest: Interest in project outcome
        sentiment: Current attitude toward project
        notes: Free-form observations
        strategic_plan: AI-generated communication strategy
        approval_role: Role in approval workflow
        notify_on_approval_needed: Send email notifications
        project_id: FK to parent project
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "stakeholders"

    # ==================== Primary Key ====================

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Stakeholder ID",
    )

    # ==================== Identity ====================

    name: str = Field(
        max_length=200,
        sa_column=Column(String(200), nullable=False),
        description="Stakeholder's full name",
    )

    role: str = Field(
        max_length=200,
        sa_column=Column(String(200), nullable=False),
        description="Job title or role (e.g., 'CTO', 'Lead Developer')",
    )

    department: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Organizational department",
    )

    email: Optional[str] = Field(
        default=None,
        max_length=255,
        index=True,
        description="Contact email for notifications",
    )

    # ==================== Analysis ====================

    influence: InfluenceLevel = Field(
        default=InfluenceLevel.MEDIUM,
        index=True,
        description="Organizational influence level (High/Medium/Low)",
    )

    interest: InterestLevel = Field(
        default=InterestLevel.MEDIUM,
        index=True,
        description="Interest in project outcome (High/Medium/Low)",
    )

    sentiment: Sentiment = Field(
        default=Sentiment.NEUTRAL,
        index=True,
        description="Current attitude toward project",
    )

    # ==================== Context ====================

    notes: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="Free-form observations about stakeholder",
    )

    strategic_plan: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="AI-generated communication strategy (Markdown)",
    )

    concerns: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="Key concerns that need to be addressed",
    )

    motivations: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="What motivates this stakeholder (for alignment)",
    )

    # ==================== Approval Workflow ====================

    approval_role: Optional[str] = Field(
        default=None,
        max_length=100,
        index=True,
        description="Role in approval workflow (e.g., 'tech_lead', 'cto', 'security_lead')",
    )

    notify_on_approval_needed: bool = Field(
        default=True,
        description="Send email notification when assigned as gate approver",
    )

    # ==================== Foreign Keys ====================

    project_id: int = Field(
        foreign_key="projects.id",
        index=True,
        nullable=False,
        description="Parent project ID",
    )

    # ==================== Timestamps ====================

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        description="Creation timestamp (UTC)",
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc).replace(tzinfo=None)
        },
        description="Last update timestamp (UTC)",
    )

    # ==================== Relationships ====================

    project: "Project" = Relationship(
        back_populates="analysis_stakeholders",
        sa_relationship_kwargs={"lazy": "joined"},
    )

    # ==================== Indexes ====================

    __table_args__ = (
        Index("idx_stakeholder_project_sentiment", "project_id", "sentiment"),
        Index("idx_stakeholder_project_influence", "project_id", "influence"),
        Index("idx_stakeholder_approval_role", "approval_role", "project_id"),
    )

    # ==================== Helper Methods ====================

    @property
    def power_interest_quadrant(self) -> str:
        """
        Get Mendelow's Matrix quadrant for this stakeholder.

        Quadrants:
            Manage Closely:  High influence, High interest
            Keep Satisfied:  High influence, Low interest
            Keep Informed:   Low influence, High interest
            Monitor:         Low influence, Low interest

        Returns:
            str: Quadrant name
        """
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
        """
        Calculate overall risk level based on influence and sentiment.

        Returns:
            str: Risk level (Critical/High/Medium/Low)
        """
        sentiment_risk = self.sentiment.risk_score
        influence_weight = self.influence.weight

        risk_score = sentiment_risk * influence_weight

        if risk_score >= 12:
            return "Critical"
        elif risk_score >= 8:
            return "High"
        elif risk_score >= 4:
            return "Medium"
        else:
            return "Low"

    @property
    def is_blocker(self) -> bool:
        """Check if stakeholder is blocking the project."""
        return self.sentiment == Sentiment.BLOCKER

    @property
    def is_champion(self) -> bool:
        """Check if stakeholder is actively championing the project."""
        return self.sentiment == Sentiment.CHAMPION

    @property
    def needs_attention(self) -> bool:
        """
        Check if stakeholder needs immediate attention.

        Criteria:
            - High influence + negative sentiment
            - Blocker regardless of influence
        """
        return (
            self.sentiment.is_negative and self.influence == InfluenceLevel.HIGH
        ) or self.is_blocker

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<Stakeholder("
            f"id={self.id}, "
            f"name={self.name!r}, "
            f"sentiment={self.sentiment.value}"
            f")>"
        )

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"{self.name} ({self.role})"
