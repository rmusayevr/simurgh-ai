"""
Admin — Token Usage endpoint.

GET /admin/token-usage
    Returns aggregated Anthropic API usage grouped by operation and by user,
    plus a daily cost series for the last 30 days.
"""

from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func, col

from app.api.v1.dependencies import get_current_superuser, get_session
from app.models.token_usage import TokenUsageRecord
from app.models.user import User
from app.schemas.token_usage import (
    DailyStat,
    OperationStat,
    TokenUsageSummary,
    UserStat,
)

router = APIRouter(tags=["admin"])


@router.get("/token-usage", response_model=TokenUsageSummary)
async def get_token_usage(
    current_user: Annotated[User, Depends(get_current_superuser)],
    session: AsyncSession = Depends(get_session),
    days: int = 30,
):
    """
    Aggregated token usage and cost breakdown for the last N days.

    Args:
        days: Number of days to look back (default 30, max 365)
    """
    days = min(days, 365)
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    # ── Totals ────────────────────────────────────────────────────────────────
    totals_result = await session.exec(
        select(
            func.count(TokenUsageRecord.id).label("calls"),
            func.coalesce(func.sum(TokenUsageRecord.cost_usd), 0).label("cost"),
            func.coalesce(func.sum(TokenUsageRecord.input_tokens), 0).label("input"),
            func.coalesce(func.sum(TokenUsageRecord.output_tokens), 0).label("output"),
            func.coalesce(func.sum(TokenUsageRecord.cache_creation_tokens), 0).label(
                "cache_create"
            ),
            func.coalesce(func.sum(TokenUsageRecord.cache_read_tokens), 0).label(
                "cache_read"
            ),
        ).where(TokenUsageRecord.created_at >= since)
    )
    totals = totals_result.one()

    # ── By operation ──────────────────────────────────────────────────────────
    ops_result = await session.exec(
        select(
            TokenUsageRecord.operation,
            func.count(TokenUsageRecord.id).label("calls"),
            func.coalesce(func.sum(TokenUsageRecord.input_tokens), 0).label("input"),
            func.coalesce(func.sum(TokenUsageRecord.output_tokens), 0).label("output"),
            func.coalesce(func.sum(TokenUsageRecord.cache_creation_tokens), 0).label(
                "cache_create"
            ),
            func.coalesce(func.sum(TokenUsageRecord.cache_read_tokens), 0).label(
                "cache_read"
            ),
            func.coalesce(func.sum(TokenUsageRecord.cost_usd), 0).label("cost"),
        )
        .where(TokenUsageRecord.created_at >= since)
        .group_by(TokenUsageRecord.operation)
        .order_by(func.sum(TokenUsageRecord.cost_usd).desc())
    )
    by_operation = [
        OperationStat(
            operation=row.operation,
            calls=row.calls,
            input_tokens=row.input,
            output_tokens=row.output,
            cache_creation_tokens=row.cache_create,
            cache_read_tokens=row.cache_read,
            cost_usd=round(row.cost, 6),
        )
        for row in ops_result.all()
    ]

    # ── By user ───────────────────────────────────────────────────────────────
    users_result = await session.exec(
        select(
            TokenUsageRecord.user_id,
            func.count(TokenUsageRecord.id).label("calls"),
            func.coalesce(func.sum(TokenUsageRecord.cost_usd), 0).label("cost"),
        )
        .where(TokenUsageRecord.created_at >= since)
        .group_by(TokenUsageRecord.user_id)
        .order_by(func.sum(TokenUsageRecord.cost_usd).desc())
        .limit(20)
    )
    user_rows = users_result.all()

    # Fetch emails for user IDs
    user_ids = [r.user_id for r in user_rows if r.user_id is not None]
    email_map: dict = {}
    if user_ids:
        email_result = await session.exec(
            select(User.id, User.email).where(col(User.id).in_(user_ids))
        )
        email_map = {row.id: row.email for row in email_result.all()}

    by_user = [
        UserStat(
            user_id=row.user_id,
            email=(
                email_map.get(row.user_id, "background task")
                if row.user_id
                else "background task"
            ),
            calls=row.calls,
            cost_usd=round(row.cost, 6),
        )
        for row in user_rows
    ]

    # ── Daily series ──────────────────────────────────────────────────────────
    daily_result = await session.exec(
        select(
            func.date_trunc("day", TokenUsageRecord.created_at).label("day"),
            func.count(TokenUsageRecord.id).label("calls"),
            func.coalesce(func.sum(TokenUsageRecord.cost_usd), 0).label("cost"),
        )
        .where(TokenUsageRecord.created_at >= since)
        .group_by(func.date_trunc("day", TokenUsageRecord.created_at))
        .order_by(func.date_trunc("day", TokenUsageRecord.created_at))
    )
    daily = [
        DailyStat(
            date=row.day.strftime("%Y-%m-%d"),
            cost_usd=round(row.cost, 6),
            calls=row.calls,
        )
        for row in daily_result.all()
    ]

    return TokenUsageSummary(
        total_calls=totals.calls or 0,
        total_cost_usd=round(totals.cost or 0, 6),
        total_input_tokens=totals.input or 0,
        total_output_tokens=totals.output or 0,
        total_cache_creation_tokens=totals.cache_create or 0,
        total_cache_read_tokens=totals.cache_read or 0,
        by_operation=by_operation,
        by_user=by_user,
        daily=daily,
    )
