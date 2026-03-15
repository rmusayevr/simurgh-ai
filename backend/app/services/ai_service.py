"""
Backward compatibility shim for ai_service.

This module has been moved to app.services.ai.base.
Please update imports to use: from app.services.ai import ai_service
"""

from anthropic import AsyncAnthropic
from app.core.config import settings
from app.services.ai import ai_service
from app.services.ai import AIService
from app.services.ai import token_usage_service
from app.services.ai import TokenUsageService
from app.services.ai import proposal_generation_service
from app.services.ai import ProposalGenerationService


class AIServiceCompat(AIService):
    """
    Backward-compatible AIService that exposes TokenUsageService attributes.

    This class maintains backward compatibility for tests and existing code
    that expects usage tracking attributes on AIService.
    """

    def __init__(self):
        super().__init__()
        self._proposal_service = proposal_generation_service

    @property
    def usage_tracker(self):
        """Delegate to TokenUsageService."""
        return token_usage_service.usage_tracker

    def _track_usage(self, usage, operation="unknown", model="", user_id=None):
        """Delegate to TokenUsageService."""
        return token_usage_service.track_usage(usage, operation, model, user_id)

    def get_usage_stats(self):
        """Delegate to TokenUsageService."""
        return token_usage_service.get_usage_stats()

    def reset_usage_stats(self):
        """Delegate to TokenUsageService."""
        return token_usage_service.reset_usage_stats()

    @property
    def _pending_tasks(self):
        """Delegate to TokenUsageService."""
        return token_usage_service._pending_tasks

    @property
    def _on_persist_done(self):
        """Delegate to TokenUsageService."""
        return token_usage_service._on_persist_done

    async def _persist_usage(self, *args, **kwargs):
        """Delegate to TokenUsageService."""
        return await token_usage_service._persist_usage(*args, **kwargs)

    @property
    def INPUT_COST_PER_MILLION(self):
        """Delegate to TokenUsageService."""
        return TokenUsageService.INPUT_COST_PER_MILLION

    @property
    def OUTPUT_COST_PER_MILLION(self):
        """Delegate to TokenUsageService."""
        return TokenUsageService.OUTPUT_COST_PER_MILLION

    @property
    def CACHE_READ_COST_PER_MILLION(self):
        """Delegate to TokenUsageService."""
        return TokenUsageService.CACHE_READ_COST_PER_MILLION

    @property
    def CACHE_WRITE_COST_PER_MILLION(self):
        """Delegate to TokenUsageService."""
        return TokenUsageService.CACHE_WRITE_COST_PER_MILLION

    async def _conduct_debate(self, *args, **kwargs):
        """Delegate to ProposalGenerationService."""
        return await self._proposal_service._conduct_debate(*args, **kwargs)

    async def _generate_persona_proposal(self, *args, **kwargs):
        """Delegate to ProposalGenerationService."""
        return await self._proposal_service._generate_persona_proposal(*args, **kwargs)

    async def generate_three_proposals(self, *args, **kwargs):
        """Delegate to ProposalGenerationService."""
        return await self._proposal_service.generate_three_proposals(*args, **kwargs)

    def _build_variation_schema(self, *args, **kwargs):
        """Delegate to ProposalGenerationService."""
        return self._proposal_service._build_variation_schema(*args, **kwargs)

    async def generate_single_variation(self, *args, **kwargs):
        """Delegate to ProposalGenerationService."""
        return await self._proposal_service.generate_single_variation(*args, **kwargs)

    async def generate_council_variations(self, *args, **kwargs):
        """Delegate to ProposalGenerationService."""
        return await self._proposal_service.generate_council_variations(*args, **kwargs)


__all__ = [
    "ai_service",
    "AIService",
    "AIServiceCompat",
    "AsyncAnthropic",
    "settings",
    "token_usage_service",
    "TokenUsageService",
    "proposal_generation_service",
    "ProposalGenerationService",
]
