"""
Token usage tracking model.

Persists per-request Anthropic API usage to the database so costs and
consumption can be analysed across server restarts, deployments, and users.

Each call to generate_text / generate_structured / generate_stream writes
one TokenUsageRecord row via AIService._persist_usage().
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import Index


class TokenUsageRecord(SQLModel, table=True):
    """
    Persisted record of a single Anthropic API call.

    Attributes:
        id: Auto-increment primary key
        user_id: User that triggered the request (nullable for background tasks)
        operation: High-level operation name (e.g. "debate_turn", "strategy")
        model: Claude model string used
        input_tokens: Prompt + cached read tokens billed at input rate
        output_tokens: Completion tokens
        cache_creation_tokens: New cache-write tokens (billed at 1.25× input)
        cache_read_tokens: Cache-hit tokens (billed at 0.1× input)
        cost_usd: Calculated USD cost for this request
        created_at: UTC timestamp of the API call
    """

    __tablename__ = "token_usage_records"

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        description="User that triggered this request (null for background/Celery tasks)",
    )

    operation: str = Field(
        max_length=100,
        description="Logical operation name (e.g. debate_turn, strategy, proposal)",
    )

    model: str = Field(
        max_length=100,
        description="Claude model string used for this request",
    )

    input_tokens: int = Field(default=0, ge=0, description="Prompt tokens billed")
    output_tokens: int = Field(default=0, ge=0, description="Completion tokens billed")
    cache_creation_tokens: int = Field(
        default=0, ge=0, description="New prompt-cache write tokens"
    )
    cache_read_tokens: int = Field(
        default=0, ge=0, description="Cache-hit tokens (cheap reads)"
    )

    cost_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="Estimated USD cost for this request",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
        description="UTC timestamp of the API call",
    )

    __table_args__ = (
        Index("idx_token_usage_user", "user_id", "created_at"),
        Index("idx_token_usage_operation", "operation", "created_at"),
    )
