"""
Admin - Settings and prompt management endpoints.

GET /admin/settings
PATCH /admin/settings
GET /admin/prompts
POST /admin/prompts
PATCH /admin/prompts/{prompt_id}
DELETE /admin/prompts/{prompt_id}
"""

import structlog
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session
from app.core.exceptions import NotFoundException, BadRequestException
from app.models.prompt import PromptTemplate
from app.schemas.prompt import (
    PromptTemplateCreate,
    PromptTemplateRead,
    PromptTemplateUpdate,
)
from app.schemas.settings import SettingsRead, SettingsUpdate
from app.services.system_service import SystemService

logger = structlog.get_logger()
router = APIRouter()


@router.get("/settings", response_model=SettingsRead)
async def get_settings(
    session: AsyncSession = Depends(get_session),
):
    """
    Get current system settings.
    """
    system_service = SystemService(session)
    settings = await system_service.get_settings()
    return settings


@router.patch("/settings", response_model=SettingsRead)
async def update_settings(
    settings_update: SettingsUpdate,
    session: AsyncSession = Depends(get_session),
):
    """
    Update system settings.
    """
    system_service = SystemService(session)

    updated_settings = await system_service.update_settings(
        **settings_update.model_dump(exclude_unset=True)
    )

    return updated_settings


@router.get("/prompts", response_model=List[PromptTemplateRead])
async def list_prompts(
    session: AsyncSession = Depends(get_session),
):
    """
    List all prompt templates (AI personas).
    """
    result = await session.exec(select(PromptTemplate).order_by(PromptTemplate.slug))
    return result.all()


@router.post("/prompts", response_model=PromptTemplateRead)
async def create_prompt(
    prompt_in: PromptTemplateCreate,
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new prompt template.
    """
    existing = await session.exec(
        select(PromptTemplate).where(PromptTemplate.slug == prompt_in.slug)
    )
    if existing.first():
        raise BadRequestException(f"Prompt with slug '{prompt_in.slug}' already exists")

    template = PromptTemplate.model_validate(prompt_in)
    session.add(template)
    await session.commit()
    await session.refresh(template)

    logger.info("prompt_template_created", slug=template.slug)
    return template


@router.patch("/prompts/{prompt_id}", response_model=PromptTemplateRead)
async def update_prompt(
    prompt_id: int,
    prompt_update: PromptTemplateUpdate,
    session: AsyncSession = Depends(get_session),
):
    """
    Update a prompt template.
    """
    template = await session.get(PromptTemplate, prompt_id)
    if not template:
        raise NotFoundException(f"Prompt template {prompt_id} not found")

    update_data = prompt_update.model_dump(exclude_unset=True)

    if "slug" in update_data and update_data["slug"] != template.slug:
        existing = await session.exec(
            select(PromptTemplate).where(PromptTemplate.slug == update_data["slug"])
        )
        if existing.first():
            raise BadRequestException(f"Slug '{update_data['slug']}' already exists")

    for key, value in update_data.items():
        setattr(template, key, value)

    template.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(template)
    await session.commit()
    await session.refresh(template)

    logger.info("prompt_template_updated", prompt_id=prompt_id)
    return template


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Delete a prompt template.
    """
    template = await session.get(PromptTemplate, prompt_id)
    if not template:
        raise NotFoundException(f"Prompt template {prompt_id} not found")

    await session.delete(template)
    await session.commit()

    logger.info("prompt_template_deleted", prompt_id=prompt_id)
    return {"success": True, "message": "Prompt template deleted"}
