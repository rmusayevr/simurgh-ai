"""
System settings service for global configuration management.

Manages the singleton SystemSettings record:
    - Maintenance mode
    - Registration policy
    - AI configuration (model, tokens, temperature)
    - Feature flags (debate, RAG, thesis mode)
    - Email configuration
    - File upload limits
    - Rate limiting

SystemSettings is a singleton — only one row exists in the table (id=1).
Auto-initializes on first access if database is fresh.
"""

import structlog
from typing import Optional
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.settings import SystemSettings
from app.core.exceptions import InternalServerException, BadRequestException

logger = structlog.get_logger()


class SystemService:
    """
    Service for managing global system settings.

    All methods operate on the singleton SystemSettings record (id=1).
    Auto-initializes settings on first access using environment defaults.
    """

    SETTINGS_ID = 1  # Singleton row ID

    def __init__(self, session: AsyncSession):
        self.session = session

    # ==================== Read ====================

    async def get_settings(self) -> SystemSettings:
        """
        Retrieve global system settings.

        Auto-initializes the settings row if database is fresh,
        using defaults from environment variables (app.core.config).

        Returns:
            SystemSettings: The singleton settings record

        Raises:
            InternalServerException: If database access fails
        """
        try:
            result = await self.session.exec(
                select(SystemSettings).where(SystemSettings.id == self.SETTINGS_ID)
            )
            settings = result.first()

            if not settings:
                logger.info("initializing_default_system_settings")
                settings = await self._initialize_defaults()

            return settings

        except Exception as e:
            logger.error("get_settings_failed", error=str(e))
            raise InternalServerException(
                "System configuration is unavailable",
                detail={"error": str(e)},
            )

    async def _initialize_defaults(self) -> SystemSettings:
        """
        Create the singleton settings row with environment defaults.
        Called automatically when the database is fresh.
        """
        from app.core.config import settings as env_settings

        try:
            defaults = SystemSettings(
                id=self.SETTINGS_ID,
                maintenance_mode=env_settings.MAINTENANCE_MODE,
                allow_registrations=True,
                ai_model=env_settings.ANTHROPIC_MODEL,
                ai_max_tokens=env_settings.ANTHROPIC_MAX_TOKENS,
                ai_temperature=env_settings.ANTHROPIC_TEMPERATURE,
                debate_feature_enabled=env_settings.ENABLE_DEBATE_FEATURE,
                rag_enabled=env_settings.ENABLE_RAG,
                thesis_mode=env_settings.THESIS_MODE,
                email_notifications_enabled=env_settings.EMAIL_ENABLED,
                max_upload_size_mb=env_settings.MAX_UPLOAD_SIZE_MB,
                rate_limit_per_minute=env_settings.RATE_LIMIT_PER_MINUTE,
            )

            self.session.add(defaults)
            await self.session.commit()
            await self.session.refresh(defaults)

            logger.info("default_system_settings_created")
            return defaults

        except Exception as e:
            await self.session.rollback()
            logger.error("initialize_defaults_failed", error=str(e))
            raise InternalServerException(
                "Failed to initialize system settings",
                detail={"error": str(e)},
            )

    # ==================== General Update ====================

    async def update_settings(
        self,
        maintenance_mode: Optional[bool] = None,
        allow_registrations: Optional[bool] = None,
        maintenance_message: Optional[str] = None,
        ai_model: Optional[str] = None,
        ai_max_tokens: Optional[int] = None,
        ai_temperature: Optional[float] = None,
        max_debate_turns: Optional[int] = None,
        debate_consensus_threshold: Optional[float] = None,
        debate_feature_enabled: Optional[bool] = None,
        rag_enabled: Optional[bool] = None,
        thesis_mode_enabled: Optional[bool] = None,
        email_notifications_enabled: Optional[bool] = None,
        max_upload_size_mb: Optional[int] = None,
        allowed_file_types: Optional[str] = None,
        rate_limit_enabled: Optional[bool] = None,
        rate_limit_per_minute: Optional[int] = None,
    ) -> SystemSettings:
        """
        Update multiple system settings at once.

        Only provided fields are updated (None = no change).

        Args:
            maintenance_mode: Enable/disable maintenance mode
            allow_registrations: Allow/block new user registrations
            maintenance_message: Custom message shown during maintenance
            ai_model: Claude model string (e.g., "claude-sonnet-4-20250514")
            ai_max_tokens: Max tokens for AI responses
            ai_temperature: AI temperature (0.0-1.0)
            debate_feature_enabled: Enable/disable multi-agent debates
            rag_enabled: Enable/disable RAG document processing
            thesis_mode: Enable/disable thesis evaluation features
            email_notifications_enabled: Enable/disable email notifications
            max_upload_size_mb: Max file upload size in MB
            rate_limit_per_minute: API rate limit per user per minute

        Returns:
            SystemSettings: Updated settings

        Raises:
            BadRequestException: If validation fails
            InternalServerException: If update fails
        """
        settings_obj = await self.get_settings()

        try:
            # Apply updates only for provided fields
            if maintenance_mode is not None:
                settings_obj.maintenance_mode = maintenance_mode
                logger.warning(
                    "maintenance_mode_toggled",
                    enabled=maintenance_mode,
                )

            if allow_registrations is not None:
                settings_obj.allow_registrations = allow_registrations

            if maintenance_message is not None:
                settings_obj.maintenance_message = maintenance_message

            if ai_model is not None:
                settings_obj.ai_model = ai_model

            if ai_max_tokens is not None:
                if ai_max_tokens <= 0:
                    raise BadRequestException("ai_max_tokens must be positive")
                settings_obj.ai_max_tokens = ai_max_tokens

            if ai_temperature is not None:
                if not 0.0 <= ai_temperature <= 2.0:
                    raise BadRequestException(
                        "ai_temperature must be between 0.0 and 2.0"
                    )
                settings_obj.ai_temperature = ai_temperature

            if max_debate_turns is not None:
                if max_debate_turns <= 0:
                    raise BadRequestException("max_debate_turns must be positive")
                settings_obj.max_debate_turns = max_debate_turns

            if debate_consensus_threshold is not None:
                if not 0.0 <= debate_consensus_threshold <= 1.0:
                    raise BadRequestException(
                        "debate_consensus_threshold must be between 0.0 and 1.0"
                    )
                settings_obj.debate_consensus_threshold = debate_consensus_threshold

            if debate_feature_enabled is not None:
                settings_obj.debate_feature_enabled = debate_feature_enabled

            if rag_enabled is not None:
                settings_obj.rag_enabled = rag_enabled

            # thesis_mode_enabled is the model field name used by the admin schema
            if thesis_mode_enabled is not None:
                settings_obj.thesis_mode_enabled = thesis_mode_enabled

            if email_notifications_enabled is not None:
                settings_obj.email_notifications_enabled = email_notifications_enabled

            if max_upload_size_mb is not None:
                if max_upload_size_mb <= 0:
                    raise BadRequestException("max_upload_size_mb must be positive")
                settings_obj.max_upload_size_mb = max_upload_size_mb

            if allowed_file_types is not None:
                settings_obj.allowed_file_types = allowed_file_types

            if rate_limit_enabled is not None:
                settings_obj.rate_limit_enabled = rate_limit_enabled

            if rate_limit_per_minute is not None:
                if rate_limit_per_minute <= 0:
                    raise BadRequestException("rate_limit_per_minute must be positive")
                settings_obj.rate_limit_per_minute = rate_limit_per_minute

            self.session.add(settings_obj)
            await self.session.commit()
            await self.session.refresh(settings_obj)

            logger.info("system_settings_updated")
            return settings_obj

        except BadRequestException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error("update_settings_failed", error=str(e))
            raise InternalServerException(
                "Failed to update system settings",
                detail={"error": str(e)},
            )
