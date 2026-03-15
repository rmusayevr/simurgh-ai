from typing import Optional, List

from pydantic import BaseModel


class OperationStat(BaseModel):
    operation: str
    calls: int
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    cost_usd: float


class UserStat(BaseModel):
    user_id: Optional[int]
    email: Optional[str]
    calls: int
    cost_usd: float


class DailyStat(BaseModel):
    date: str
    cost_usd: float
    calls: int


class TokenUsageSummary(BaseModel):
    total_calls: int
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    total_cache_creation_tokens: int
    total_cache_read_tokens: int
    by_operation: List[OperationStat]
    by_user: List[UserStat]
    daily: List[DailyStat]
