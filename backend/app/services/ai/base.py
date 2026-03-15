"""
AI service for Claude API interactions.

Provides unified interface for:
    - Text generation with retry logic
    - Structured outputs via tool use
    - Streaming responses
    - Strategy generation for stakeholder engagement
    - Persona chat (Deep-Dive Debate Mode)

Features:
    - Extended thinking for complex reasoning
    - Prompt caching for cost optimization
    - Exponential backoff retry on rate limits
    - Input validation and sanitization
    - Comprehensive logging with structlog
"""

import structlog
from typing import Any, Dict, List, Optional, AsyncIterator, Tuple

from anthropic import AsyncAnthropic, RateLimitError, APIError, APITimeoutError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.exceptions import AIServiceException, BadRequestException
from app.models.prompt import PromptTemplate
from app.services.ai.token_usage import token_usage_service

logger = structlog.get_logger()


class AIService:
    """
    Unified AI service for all Claude API interactions.

    Singleton pattern is acceptable here since:
        1. AsyncAnthropic client manages connection pooling internally
        2. Token usage tracking is handled by TokenUsageService
        3. No per-request state stored
    """

    def __init__(self):
        try:
            api_key = settings.ANTHROPIC_API_KEY.get_secret_value()
        except Exception as e:
            logger.critical("anthropic_api_key_missing", error=str(e))
            raise ValueError("ANTHROPIC_API_KEY not configured") from e

        self.client = AsyncAnthropic(api_key=api_key)
        self.default_model = settings.ANTHROPIC_MODEL

    @property
    def usage_tracker(self) -> Dict[str, Any]:
        """Delegate to TokenUsageService for backward compatibility."""
        return token_usage_service.usage_tracker

    def _track_usage(
        self,
        usage: Any,
        operation: str = "unknown",
        model: str = "",
        user_id: Optional[int] = None,
    ) -> None:
        """Track token usage (delegated to TokenUsageService)."""
        token_usage_service.track_usage(usage, operation, model, user_id)

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics (delegated to TokenUsageService)."""
        return token_usage_service.get_usage_stats()

    def reset_usage_stats(self) -> None:
        """Reset usage statistics (delegated to TokenUsageService)."""
        token_usage_service.reset_usage_stats()

    @staticmethod
    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        before_sleep=lambda retry_state: logger.warning(
            "ai_api_retry",
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception()),
        ),
    )
    def _retry_strategy():
        """Shared retry configuration for all API calls."""
        pass

    def _validate_and_sanitize_input(
        self, user_input: str, max_length: int = 50000
    ) -> str:
        """Validate and sanitize user input."""
        if not user_input or not user_input.strip():
            raise BadRequestException("Input cannot be empty")

        if len(user_input) > max_length:
            raise BadRequestException(
                f"Input exceeds maximum length of {max_length} characters"
            )

        sanitized = user_input.strip()

        suspicious_patterns = [
            "ignore previous instructions",
            "disregard system prompt",
            "you are now",
            "forget everything",
            "new instructions:",
        ]

        lower_input = sanitized.lower()
        for pattern in suspicious_patterns:
            if pattern in lower_input:
                logger.warning(
                    "prompt_injection_detected",
                    pattern=pattern,
                    input_preview=sanitized[:100],
                )
                raise BadRequestException(
                    "Input contains suspicious patterns. Please rephrase your request."
                )

        return sanitized

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        before_sleep=lambda retry_state: logger.warning(
            "ai_api_retry",
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception()),
        ),
    )
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        use_extended_thinking: bool = False,
        use_caching: bool = False,
        operation: str = "generate_text",
        user_id: Optional[int] = None,
    ) -> str:
        """Generate text using Claude API."""
        model = model or self.default_model
        user_prompt = self._validate_and_sanitize_input(user_prompt)

        if use_caching:
            system = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system = system_prompt

        extra_params = {}
        if use_extended_thinking and "sonnet" in model.lower():
            extra_params["thinking"] = {"type": "enabled", "budget_tokens": 10000}

        try:
            response = await self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user_prompt}],
                **extra_params,
            )

            if use_extended_thinking:
                for block in response.content:
                    if block.type == "thinking":
                        logger.info(
                            "extended_thinking_used",
                            thinking_length=len(block.thinking),
                        )

            token_usage_service.track_usage(
                response.usage, operation=operation, model=model, user_id=user_id
            )

            text_content = ""
            for block in response.content:
                if block.type == "text":
                    text_content += block.text

            return text_content

        except (RateLimitError, APITimeoutError, APIError) as e:
            logger.error("ai_request_failed_after_retries", error=str(e), model=model)
            raise AIServiceException(f"AI service error: {str(e)}")
        except Exception as e:
            logger.error("ai_request_unexpected_error", error=str(e), model=model)
            raise AIServiceException(f"Unexpected AI error: {str(e)}")

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        before_sleep=lambda retry_state: logger.warning(
            "ai_api_retry",
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception()),
        ),
    )
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        tool_name: str = "submit_response",
        model: Optional[str] = None,
        max_tokens: int = 4000,
        operation: str = "generate_structured",
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate structured JSON output using tool use."""
        model = model or self.default_model
        user_prompt = self._validate_and_sanitize_input(user_prompt)

        try:
            response = await self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[
                    {
                        "name": tool_name,
                        "description": f"Submit {tool_name} with structured data",
                        "input_schema": schema,
                    }
                ],
                tool_choice={"type": "tool", "name": tool_name},
            )

            token_usage_service.track_usage(
                response.usage, operation=operation, model=model, user_id=user_id
            )

            for block in response.content:
                if block.type == "tool_use" and block.name == tool_name:
                    return block.input

            logger.error("no_tool_use_found")
            raise AIServiceException("AI did not return structured output")

        except Exception as e:
            logger.error("structured_output_failed", error=str(e))
            raise AIServiceException(f"Structured output error: {str(e)}")

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        operation: str = "generate_stream",
        user_id: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Stream text generation for real-time feedback."""
        model = model or self.default_model
        user_prompt = self._validate_and_sanitize_input(user_prompt)

        try:
            async with self.client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text

                final_message = await stream.get_final_message()
                token_usage_service.track_usage(
                    final_message.usage,
                    operation=operation,
                    model=model,
                    user_id=user_id,
                )

        except Exception as e:
            logger.error("streaming_failed", error=str(e))
            raise AIServiceException(f"Streaming error: {str(e)}")

    async def get_persona_template(
        self, slug: str, session: AsyncSession
    ) -> Optional[PromptTemplate]:
        """Fetch prompt template from database by slug."""
        result = await session.exec(
            select(PromptTemplate).where(
                PromptTemplate.slug == slug,
                PromptTemplate.is_active,
            )
        )
        return result.first()

    def build_strategy_prompt(
        self,
        stakeholder: Any,
        project: Any,
        extra_context: str = "",
    ) -> str:
        """Build prompt for stakeholder engagement strategy generation."""
        return f"""
Analyze the following situation and provide a strategic outreach plan.

PROJECT: {project.name}
DESCRIPTION: {project.description}

TARGET STAKEHOLDER:
- Name: {stakeholder.name}
- Role: {stakeholder.role}
- Department: {stakeholder.department or "Unknown"}
- Matrix Position: Influence is {stakeholder.influence}, Interest is {stakeholder.interest}
- Current Sentiment: {stakeholder.sentiment}

ADDITIONAL NOTES:
{stakeholder.notes or "None"}
{extra_context}

OUTPUT REQUIREMENTS:
1. **Psychological Profile**: What likely motivates this person?
2. **Strategic Approach**: Direct, data-driven, empathetic, or formal?
3. **Key Talking Points**: 3 bullets aligning project success with THEIR success
4. **Sample Outreach**: Ready-to-use email or Slack message
5. **Anticipated Objections**: What concerns might they raise?
6. **Success Metrics**: How will we know if this worked?

Format with clear markdown headers.
""".strip()

    async def generate_strategy(
        self,
        prompt: str,
        model: Optional[str] = None,
        use_extended_thinking: bool = False,
        user_id: Optional[int] = None,
    ) -> str:
        """Generate stakeholder engagement strategy with token tracking."""
        logger.info("strategy_generation_started", prompt_length=len(prompt))

        system_prompt = """You are a Master Corporate Strategist specializing in stakeholder 
management and organizational change. Provide actionable, psychologically informed strategies 
combining insights from organizational psychology, change management, political dynamics, and 
influence techniques. Be practical, empathetic, and results-driven."""

        return await self.generate_text(
            system_prompt=system_prompt,
            user_prompt=prompt,
            model=model,
            max_tokens=2000,
            temperature=0.7,
            use_extended_thinking=use_extended_thinking,
            operation="stakeholder_strategy",
            user_id=user_id,
        )

    async def generate_strategy_stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Stream strategy generation for real-time feedback."""
        system_prompt = """You are a Master Corporate Strategist specializing in stakeholder 
management. Provide actionable, psychologically informed strategies."""

        async for chunk in self.generate_stream(
            system_prompt=system_prompt,
            user_prompt=prompt,
            model=model,
            max_tokens=2000,
            temperature=0.7,
            operation="stakeholder_strategy_stream",
            user_id=user_id,
        ):
            yield chunk

    async def chat_with_persona(
        self,
        persona_name: str,
        proposal_content: str,
        original_task: str,
        user_message: str,
        history: List[Dict[str, str]],
        model: Optional[str] = None,
    ) -> Tuple[str, List[Dict[str, str]]]:
        """Chat with a persona about their proposal."""
        logger.info("persona_chat_started", persona=persona_name)

        user_message = self._validate_and_sanitize_input(user_message, max_length=5000)

        MAX_HISTORY_TURNS = 10
        trimmed_history = (
            history[-MAX_HISTORY_TURNS:]
            if len(history) > MAX_HISTORY_TURNS
            else history
        )

        system_prompt = f"""You are '{persona_name}', defending your architectural proposal.

ORIGINAL TASK: {original_task}
YOUR PROPOSAL: {proposal_content}

Answer questions about WHY you made these choices, staying in character.
Be professional, reference your proposal, acknowledge valid criticisms while defending 
your reasoning. Stay concise (2-4 paragraphs)."""

        messages = []
        for msg in trimmed_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        try:
            response = await self.client.messages.create(
                model=model or self.default_model,
                max_tokens=1000,
                temperature=0.7,
                system=system_prompt,
                messages=messages,
            )

            token_usage_service.track_usage(response.usage)
            assistant_message = response.content[0].text

            updated_history = trimmed_history + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message},
            ]

            logger.info("persona_chat_success", history_length=len(updated_history))
            return assistant_message, updated_history

        except Exception as e:
            logger.error("persona_chat_failed", error=str(e))
            raise AIServiceException(f"Persona chat error: {str(e)}")


ai_service = AIService()
