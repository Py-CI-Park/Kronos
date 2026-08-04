"""Leakage-aware cross-sectional features for post-close, next-open research."""

from __future__ import annotations

import math
from dataclasses import dataclass

from stom_rl.etf_research.data import PriceSeries


@dataclass(frozen=True, slots=True)
class RankSample:
    day: int
    code: str
    features: tuple[float, ...]
    forward_return: float


def build_rank_samples(
    series: tuple[PriceSeries, ...],
    *,
    horizons: tuple[int, ...] = (5, 10, 20),
    holding_days: int = 5,
) -> tuple[RankSample, ...]:
    """Use close data through t and measure tradable next-open forward return."""
    if not horizons or min(horizons) <= 0 or holding_days <= 0:
        raise ValueError("horizons and holding_days must be positive")
    maximum_horizon = max(horizons)
    samples: list[RankSample] = []
    for item in series:
        bars = item.bars
        final_exclusive = len(bars) - holding_days - 1
        for decision_index in range(maximum_horizon, final_exclusive):
            decision = bars[decision_index]
            returns = tuple(
                decision.close / bars[decision_index - horizon].close - 1.0
                for horizon in horizons
            )
            recent_volumes = tuple(bar.volume for bar in bars[decision_index - maximum_horizon : decision_index])
            mean_volume = sum(recent_volumes) / len(recent_volumes)
            volume_ratio = math.log1p(decision.volume) - math.log1p(mean_volume)
            entry_open = bars[decision_index + 1].open
            exit_open = bars[decision_index + holding_days + 1].open
            samples.append(
                RankSample(
                    day=decision.day,
                    code=item.code,
                    features=returns + (volume_ratio,),
                    forward_return=exit_open / entry_open - 1.0,
                )
            )
    return tuple(samples)

