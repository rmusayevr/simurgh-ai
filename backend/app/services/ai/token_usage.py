"""
Token usage tracking service for AI API interactions.

Provides:
    - In-memory usage tracking for current session
    - Asynchronous persistence of usage records to database
    - Cost calculation based on Claude pricing
"""

import asyncio
import structlog
from typing import Any, Dict, Optional

from app.models.token_usage import TokenUsageRecord

logger = structlog.get_logger()


class TokenUsageService:
    """
    Token usage tracking service.

    Singleton pattern for consistent tracking across requests.
    """

    INPUT_COST_PER_MILLION = 3.00
    OUTPUT_COST_PER_MILLION = 15.00
    CACHE_WRITE_COST_PER_MILLION = 3.75
    CACHE_READ_COST_PER_MILLION = 0.30

    def __init__(self):
        self.usage_tracker: Dict[str, Any] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
            "cost_usd": 0.0,
        }
        self._pending_tasks: set[asyncio.Task] = set()

    def track_usage(
        self,
        usage: Any,
        operation: str = "unknown",
        model: str = "",
        user_id: Optional[int] = None,
    ) -> None:
        """Track token usage, calculate costs, and fire-and-forget DB persistence."""
        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0)
        cache_read = getattr(usage, "cache_read_input_tokens", 0)

        self.usage_tracker["input_tokens"] += input_tokens
        self.usage_tracker["output_tokens"] += output_tokens
        self.usage_tracker["cache_creation_tokens"] += cache_creation
        self.usage_tracker["cache_read_tokens"] += cache_read

        input_cost = (input_tokens / 1_000_000) * self.INPUT_COST_PER_MILLION
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_COST_PER_MILLION
        cache_write_cost = (
            cache_creation / 1_000_000
        ) * self.CACHE_WRITE_COST_PER_MILLION
        cache_read_cost = (cache_read / 1_000_000) * self.CACHE_READ_COST_PER_MILLION

        request_cost = input_cost + output_cost + cache_write_cost + cache_read_cost
        self.usage_tracker["cost_usd"] += request_cost

        logger.info(
            "token_usage",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation=cache_creation,
            cache_read=cache_read,
            request_cost_usd=round(request_cost, 4),
            total_cost_usd=round(self.usage_tracker["cost_usd"], 2),
        )

        task = asyncio.create_task(
            self._persist_usage(
                operation=operation,
                model=model,
                user_id=user_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_creation_tokens=cache_creation,
                cache_read_tokens=cache_read,
                cost_usd=round(request_cost, 6),
            ),
            name=f"persist_usage:{operation}",
        )
        self._pending_tasks.add(task)
        task.add_done_callback(self._on_persist_done)

    async def _persist_usage(
        self,
        operation: str,
        model: str,
        user_id: Optional[int],
        input_tokens: int,
        output_tokens: int,
        cache_creation_tokens: int,
        cache_read_tokens: int,
        cost_usd: float,
    ) -> None:
        """Persist a single API call's usage to the database."""
        try:
            from app.db.session import async_session_factory

            async with async_session_factory() as session:
                record = TokenUsageRecord(
                    user_id=user_id,
                    operation=operation,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_creation_tokens=cache_creation_tokens,
                    cache_read_tokens=cache_read_tokens,
                    cost_usd=cost_usd,
                )
                session.add(record)
                await session.commit()
        except Exception as exc:
            logger.error("token_usage_persistence_failed", error=str(exc))

    def _on_persist_done(self, task: asyncio.Task) -> None:
        """Done-callback for persistence tasks."""
        self._pending_tasks.discard(task)
        try:
            task.result()
        except asyncio.CancelledError:
            logger.warning("token_usage_task_cancelled", task_name=task.get_name())
        except Exception as exc:
            logger.error(
                "token_usage_task_unexpected_error",
                task_name=task.get_name(),
                error=str(exc),
            )

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics (informational only)."""
        return self.usage_tracker.copy()

    def reset_usage_stats(self) -> None:
        """Reset usage statistics."""
        self.usage_tracker = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
            "cost_usd": 0.0,
        }


token_usage_service = TokenUsageService()
