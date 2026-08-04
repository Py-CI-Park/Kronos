from __future__ import annotations

import pytest

from stom_rl.daily_close_research.features import build_rank_samples
from stom_rl.etf_research.data import PriceBar, PriceSeries


def _series(code: str, growth: float, count: int = 40) -> PriceSeries:
    bars = tuple(
        PriceBar(
            day=20260101 + index,
            open=100.0 * growth**index,
            high=102.0 * growth**index,
            low=99.0 * growth**index,
            close=101.0 * growth**index,
            volume=1_000_000.0 + index,
        )
        for index in range(count)
    )
    return PriceSeries(code, bars)


def test_features_use_decision_close_and_forward_return_starts_at_next_open() -> None:
    samples = build_rank_samples((_series("000250", 1.01),), horizons=(5, 10, 20), holding_days=5)

    first = samples[0]
    assert first.day == 20260121
    assert first.code == "000250"
    assert first.features[0] == pytest.approx(1.01**5 - 1.0)
    assert first.features[2] == pytest.approx(1.01**20 - 1.0)
    assert first.forward_return == pytest.approx(1.01**5 - 1.0)


def test_insufficient_history_produces_no_samples() -> None:
    samples = build_rank_samples((_series("000250", 1.01, count=21),), horizons=(5, 10, 20), holding_days=5)

    assert samples == ()

