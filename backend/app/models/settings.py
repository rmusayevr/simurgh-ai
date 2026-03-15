"""
System settings model.

Stores application-wide configuration that can be modified at runtime
without code deployments or restarts. Settings are managed via the
admin interface and cached in middleware.

Note:
    Only ONE record should exist (singleton pattern).
    Access via SystemService.get_settings()
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field, Column, String


class SystemSettings(SQLModel, table=True):
    """
    Application-wide system settings (singleton).

    Provides runtime-configurable settings for system behavior.
    Only one record should exist (id=1).

    Attributes:
        id: Primary key (always 1)

        -- Access Control --
        maintenance_mode: Block all non-admin requests
        allow_registrations: Enable/disable new user signups

        -- AI Configuration --
        ai_model: Claude model to use
        ai_temperature: Default AI temperature
        ai_max_tokens: Default max tokens per request
        max_debate_turns: Maximum turns in debate sessions

        -- Feature Flags --
        rag_enabled: Enable RAG document processing
        debate_feature_enabled: Enable multi-agent debates
        thesis_mode_enabled: Enable thesis evaluation features

        -- Rate Limiting --
        rate_limit_enabled: Enable API rate limiting
        rate_limit_per_minute: Max requests per minute per user

        -- Email --
        email_notifications_enabled: Enable email notifications

        -- Metadata --
        updated_at: Last update timestamp
        updated_by: Admin who last updated settings
    """

    __tablename__ = "system_settings"

    # ==================== Primary Key ====================

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Settings ID (always 1 - singleton)",
    )

    # ==================== Access Control ====================

    maintenance_mode: bool = Field(
        default=False,
        description="Block all non-admin requests when True",
    )

    maintenance_message: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Custom message shown during maintenance",
    )

    allow_registrations: bool = Field(
        default=True,
        description="Allow new user registrations",
    )

    # ==================== AI Configuration ====================

    ai_model: str = Field(
        default="claude-sonnet-4-20250514",
        max_length=100,
        sa_column=Column(String(100), nullable=False),
        description="Claude model to use for AI operations",
    )

    ai_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Default AI temperature (0.0=deterministic, 1.0=creative)",
    )

    ai_max_tokens: int = Field(
        default=4096,
        gt=0,
        le=100000,
        description="Default max tokens per AI request",
    )

    max_debate_turns: int = Field(
        default=10,
        gt=0,
        le=50,
        description="Maximum turns allowed in debate sessions",
    )

    debate_consensus_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for consensus detection",
    )

    # ==================== Feature Flags ====================

    rag_enabled: bool = Field(
        default=True,
        description="Enable RAG document processing for AI context",
    )

    debate_feature_enabled: bool = Field(
        default=True,
        description="Enable multi-agent Council of Agents debates",
    )

    thesis_mode_enabled: bool = Field(
        default=False,
        description="Enable thesis evaluation features (A/B testing, questionnaires)",
    )

    # ==================== Rate Limiting ====================

    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable API rate limiting",
    )

    rate_limit_per_minute: int = Field(
        default=60,
        gt=0,
        le=10000,
        description="Maximum API requests per minute per user",
    )

    # ==================== Document Upload ====================

    max_upload_size_mb: int = Field(
        default=50,
        gt=0,
        le=500,
        description="Maximum file upload size in MB",
    )

    allowed_file_types: str = Field(
        default=".pdf,.docx,.txt,.md",
        max_length=200,
        description="Comma-separated allowed file extensions",
    )

    # ==================== Email ====================

    email_notifications_enabled: bool = Field(
        default=False,
        description="Enable email notifications",
    )

    # ==================== Timestamps ====================

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        description="Settings creation timestamp (UTC)",
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc).replace(tzinfo=None)
        },
        description="Last update timestamp (UTC)",
    )

    updated_by: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        description="Admin user who last updated settings",
    )

    # ==================== Helper Methods ====================

    @property
    def allowed_file_types_list(self) -> list:
        """Get allowed file types as list."""
        return [
            ext.strip() for ext in self.allowed_file_types.split(",") if ext.strip()
        ]

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<SystemSettings("
            f"maintenance={self.maintenance_mode}, "
            f"registrations={self.allow_registrations}, "
            f"model={self.ai_model}"
            f")>"
        )
