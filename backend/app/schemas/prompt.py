from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime

from app.models.prompt import TemplateCategory


# ==================== Prompt Template Schemas ====================


class PromptTemplateCreate(BaseModel):
    """Schema for creating a new prompt template."""

    slug: str = Field(
        min_length=1,
        max_length=100,
        description="Unique programmatic identifier (e.g., 'legacy_keeper_system')",
    )
    name: str = Field(min_length=1, max_length=200)
    category: TemplateCategory = TemplateCategory.SYSTEM
    description: Optional[str] = Field(default=None, max_length=500)
    system_prompt: str = Field(min_length=1)
    user_prompt_template: Optional[str] = Field(
        default=None,
        description="Optional user message template with {placeholders}",
    )
    model_override: Optional[str] = Field(default=None, max_length=100)
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
    is_active: bool = True

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Slugs must be lowercase with underscores only — used as programmatic keys."""
        import re

        if not re.match(r"^[a-z0-9_]+$", v):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and underscores"
            )
        return v


class PromptTemplateUpdate(BaseModel):
    """
    Schema for updating a prompt template.
    Slug is intentionally excluded — slugs are programmatic keys
    used by AI services and must not change after creation.
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    category: Optional[TemplateCategory] = None
    description: Optional[str] = Field(default=None, max_length=500)
    system_prompt: Optional[str] = Field(default=None, min_length=1)
    user_prompt_template: Optional[str] = None
    model_override: Optional[str] = Field(default=None, max_length=100)
    temperature_override: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
    )
    max_tokens_override: Optional[int] = Field(
        default=None,
        gt=0,
        le=100000,
    )
    is_active: Optional[bool] = None


class PromptTemplateListRead(BaseModel):
    """
    Lightweight template summary for list views.
    Excludes full system_prompt and user_prompt_template content.
    """

    id: int
    slug: str
    name: str
    category: TemplateCategory
    description: Optional[str]
    is_active: bool
    version: int
    model_override: Optional[str]
    temperature_override: Optional[float]
    max_tokens_override: Optional[int]
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptTemplateRead(BaseModel):
    """Full template detail including prompt content."""

    id: int
    slug: str
    name: str
    category: TemplateCategory
    description: Optional[str]
    system_prompt: str
    user_prompt_template: Optional[str]
    model_override: Optional[str]
    temperature_override: Optional[float]
    max_tokens_override: Optional[int]
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptTemplateActivate(BaseModel):
    """Schema for toggling template active state."""

    is_active: bool


class PromptTemplateVersionResponse(BaseModel):
    """Lightweight response after a version increment."""

    id: int
    slug: str
    version: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
