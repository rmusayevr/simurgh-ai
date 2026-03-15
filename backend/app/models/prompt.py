"""
Prompt template model.

Stores AI prompt templates for different use cases (debate personas,
proposal generation, stakeholder analysis, etc.).

Templates are identified by slug and can be toggled active/inactive
without code changes.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import SQLModel, Field, Column, Text, String
from sqlalchemy import Index


# ==================== Enums ====================


class TemplateCategory(str, Enum):
    """
    Category of prompt template.

    Categories:
        DEBATE: Multi-agent debate prompts
        PROPOSAL: Architecture proposal generation
        STAKEHOLDER: Stakeholder analysis
        COMMUNICATION: Stakeholder communication plans
        SYSTEM: System-level prompts
    """

    DEBATE = "debate"
    PROPOSAL = "proposal"
    STAKEHOLDER = "stakeholder"
    COMMUNICATION = "communication"
    SYSTEM = "system"


# ==================== Model ====================


class PromptTemplate(SQLModel, table=True):
    """
    AI prompt template for various system operations.

    Templates are stored in the database to allow dynamic updates
    without code deployments. Each template has a unique slug
    for programmatic access.

    Examples:
        slug="legacy_keeper_system"   → Legacy Keeper debate persona
        slug="innovator_system"       → Innovator debate persona
        slug="proposal_generation"    → Architecture proposal generation
        slug="stakeholder_analysis"   → Stakeholder communication plan

    Attributes:
        id: Primary key
        slug: Unique identifier for programmatic access
        name: Human-readable name
        category: Template category
        description: What this template is used for
        system_prompt: AI system prompt content
        user_prompt_template: Optional user message template
        model_override: Override default AI model for this template
        temperature_override: Override default temperature
        max_tokens_override: Override default max tokens
        is_active: Whether template is active
        version: Template version number
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "prompt_templates"

    # ==================== Primary Key ====================

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Template ID",
    )

    # ==================== Identity ====================

    slug: str = Field(
        sa_column=Column(
            String(100),
            nullable=False,
            unique=True,
            index=True,
        ),
        max_length=100,
        description="Unique slug for programmatic access (e.g., 'legacy_keeper_system')",
    )

    name: str = Field(
        max_length=200,
        sa_column=Column(String(200), nullable=False),
        description="Human-readable template name",
    )

    # ==================== Organization ====================

    category: TemplateCategory = Field(
        default=TemplateCategory.SYSTEM,
        index=True,
        description="Template category for filtering",
    )

    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="What this template is used for",
    )

    # ==================== Content ====================

    system_prompt: str = Field(
        sa_column=Column(Text, nullable=False),
        description="AI system prompt content",
    )

    user_prompt_template: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="Optional user message template with {placeholders}",
    )

    # ==================== AI Configuration ====================

    model_override: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Override default AI model for this template",
    )

    temperature_override: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Override default temperature (0.0-2.0)",
    )

    max_tokens_override: Optional[int] = Field(
        default=None,
        gt=0,
        le=100000,
        description="Override default max tokens",
    )

    # ==================== Status ====================

    is_active: bool = Field(
        default=True,
        index=True,
        description="Whether template is active (inactive = ignored)",
    )

    version: int = Field(
        default=1,
        description="Template version (incremented on update)",
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

    # ==================== Indexes ====================

    __table_args__ = (
        Index("idx_prompt_template_category_active", "category", "is_active"),
        Index("idx_prompt_template_slug_active", "slug", "is_active"),
    )

    # ==================== Helper Methods ====================

    def render_user_prompt(self, **kwargs) -> Optional[str]:
        """
        Render user prompt template with provided variables.

        Args:
            **kwargs: Variables to inject into template

        Returns:
            str | None: Rendered prompt or None if no template

        Example:
            >>> template.render_user_prompt(
            ...     proposal="...",
            ...     context="..."
            ... )
        """
        if not self.user_prompt_template:
            return None

        try:
            return self.user_prompt_template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}") from e

    def increment_version(self) -> None:
        """Increment version number on update."""
        self.version += 1
        self.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def deactivate(self) -> None:
        """Deactivate this template."""
        self.is_active = False
        self.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def activate(self) -> None:
        """Activate this template."""
        self.is_active = True
        self.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<PromptTemplate("
            f"slug={self.slug!r}, "
            f"category={self.category.value}, "
            f"active={self.is_active}"
            f")>"
        )

    def __str__(self) -> str:
        """Human-readable string representation."""
        return self.name
