"""
Shared helper functions for experiment data endpoints.
"""

import statistics
from typing import Optional


def _safe_mean(values: list[float]) -> Optional[float]:
    return round(statistics.mean(values), 3) if values else None


def _safe_stdev(values: list[float]) -> Optional[float]:
    return round(statistics.stdev(values), 3) if len(values) >= 2 else None


def _cohen_d(group_a: list[float], group_b: list[float]) -> Optional[float]:
    """Calculate Cohen's d effect size between two groups."""
    if len(group_a) < 2 or len(group_b) < 2:
        return None
    mean_diff = statistics.mean(group_a) - statistics.mean(group_b)
    pooled_sd = (
        (statistics.stdev(group_a) ** 2 + statistics.stdev(group_b) ** 2) / 2
    ) ** 0.5
    if pooled_sd == 0:
        return None
    return round(mean_diff / pooled_sd, 3)
