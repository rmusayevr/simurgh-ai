# ==================== settings.py ====================

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class AIConfigUpdate(BaseModel):
    """Schema for updating AI model configuration specifically."""

    ai_model: Optional[str] = Field(default=None, max_length=100)
    ai_temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    ai_max_tokens: Optional[int] = Field(default=None, gt=0, le=100000)


class MaintenanceUpdate(BaseModel):
    """Schema for toggling maintenance mode."""

    maintenance_mode: bool
    maintenance_message: Optional[str] = Field(default=None, max_length=500)


class SettingsUpdate(BaseModel):
    """
    Full settings update schema for admin panel.
    All fields optional — only provided fields are updated.
    """

    # Access Control
    maintenance_mode: Optional[bool] = None
    maintenance_message: Optional[str] = Field(default=None, max_length=500)
    allow_registrations: Optional[bool] = None

    # AI Configuration
    ai_model: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Claude model identifier (e.g., 'claude-sonnet-4-20250514')",
    )
    ai_temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    ai_max_tokens: Optional[int] = Field(default=None, gt=0, le=100000)
    max_debate_turns: Optional[int] = Field(default=None, gt=0, le=50)
    debate_consensus_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Feature Flags
    rag_enabled: Optional[bool] = None
    debate_feature_enabled: Optional[bool] = None
    thesis_mode_enabled: Optional[bool] = None

    # Rate Limiting
    rate_limit_enabled: Optional[bool] = None
    rate_limit_per_minute: Optional[int] = Field(default=None, gt=0, le=10000)

    # Document Upload
    max_upload_size_mb: Optional[int] = Field(default=None, gt=0, le=500)
    allowed_file_types: Optional[str] = Field(default=None, max_length=200)

    # Email
    email_notifications_enabled: Optional[bool] = None


class SettingsRead(BaseModel):
    """Full system settings returned to admin."""

    id: int

    # Access Control
    maintenance_mode: bool
    maintenance_message: Optional[str]
    allow_registrations: bool

    # AI Configuration
    ai_model: str
    ai_temperature: float
    ai_max_tokens: int
    max_debate_turns: int
    debate_consensus_threshold: float

    # Feature Flags
    rag_enabled: bool
    debate_feature_enabled: bool
    thesis_mode_enabled: bool

    # Rate Limiting
    rate_limit_enabled: bool
    rate_limit_per_minute: int

    # Document Upload
    max_upload_size_mb: int
    allowed_file_types: str

    # Email
    email_notifications_enabled: bool

    # Metadata
    updated_at: datetime
    updated_by: Optional[int]

    model_config = ConfigDict(from_attributes=True)

    @property
    def allowed_file_types_list(self) -> list:
        return [
            ext.strip() for ext in self.allowed_file_types.split(",") if ext.strip()
        ]
