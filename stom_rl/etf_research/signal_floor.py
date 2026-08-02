"""Chronological ETF momentum canary with shuffled-score controls."""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from statistics import fmean

from .data import PriceSeries


@dataclass(frozen=True, slots=True)
class SignalSample:
    day: int
    code: str
    score: float
    gross_return: float


@dataclass(frozen=True, slots=True)
class SignalFloorThresholds:
    round_trip_cost_bps: float
    diagnostic_round_trip_cost_bps: float
    holding_days: int
    fold_count: int
    positive_fold_minimum: int
    positive_seed_minimum: int
    native_minus_shuffle_minimum_bps: float
    maximum_drawdown_limit: float

    @classmethod
    def registered(cls) -> SignalFloorThresholds:
        return cls(23.0, 9.0, 5, 5, 4, 2, 10.0, 0.25)


@dataclass(frozen=True, slots=True)
class FoldSignalResult:
    fold_id: int
    date_count: int
    native_mean_bps: float


@dataclass(frozen=True, slots=True)
class SignalFloorReceipt:
    verdict: str
    evidence_scope: str
    sample_count: int
    date_count: int
    native_mean_bps: float
    diagnostic_9bp_native_mean_bps: float
    shuffle_mean_bps: float
    native_minus_shuffle_bps: float
    equal_weight_mean_bps: float
    positive_fold_count: int
    positive_seed_count: int
    maximum_drawdown: float
    folds: tuple[FoldSignalResult, ...]


def build_momentum_samples(
    series: tuple[PriceSeries, ...],
    *,
    lookback_days: int = 20,
    holding_days: int = 5,
) -> tuple[SignalSample, ...]:
    """Build t-1 momentum and t-open to t+h-close returns."""
    samples: list[SignalSample] = []
    for item in series:
        bars = item.bars
        for entry_index in range(lookback_days, len(bars) - holding_days + 1):
            decision_close = bars[entry_index - 1].close
            reference_close = bars[entry_index - lookback_days].close
            exit_close = bars[entry_index + holding_days - 1].close
            score = decision_close / reference_close - 1.0
            gross_return = exit_close / bars[entry_index].open - 1.0
            samples.append(SignalSample(bars[entry_index].day, item.code, score, gross_return))
    return tuple(samples)


def evaluate_signal_floor(
    samples: tuple[SignalSample, ...],
    thresholds: SignalFloorThresholds,
    *,
    shuffle_seeds: tuple[int, ...],
    evidence_scope: str = "PROMOTION_ELIGIBLE",
) -> SignalFloorReceipt:
    """Compare daily top-score trades with deterministic shuffled controls."""
    by_day: dict[int, list[SignalSample]] = defaultdict(list)
    for sample in samples:
        by_day[sample.day].append(sample)
    required_candidates = max((len(rows) for rows in by_day.values()), default=0)
    days = tuple(sorted(day for day, rows in by_day.items() if len(rows) == required_candidates))
    cost = thresholds.round_trip_cost_bps / 10_000.0
    native_gross = tuple(max(by_day[day], key=lambda row: (row.score, row.code)).gross_return for day in days)
    native_returns = tuple(value - cost for value in native_gross)
    equal_returns = tuple(fmean(row.gross_return for row in by_day[day]) - cost for day in days)
    shuffle_by_seed = tuple(_shuffle_returns(by_day, days, seed, cost) for seed in shuffle_seeds)
    shuffle_means = tuple(fmean(values) if values else 0.0 for values in shuffle_by_seed)
    native_mean = fmean(native_returns) if native_returns else 0.0
    folds = _fold_results(days, native_returns, thresholds.fold_count)
    native_mean_bps = native_mean * 10_000.0
    shuffle_mean_bps = (fmean(shuffle_means) if shuffle_means else 0.0) * 10_000.0
    delta_bps = native_mean_bps - shuffle_mean_bps
    positive_folds = sum(fold.native_mean_bps > 0 for fold in folds)
    positive_seeds = sum(native_mean > shuffled for shuffled in shuffle_means)
    drawdown = _maximum_drawdown(native_returns[:: thresholds.holding_days])
    passed = (
        native_mean_bps > 0
        and delta_bps >= thresholds.native_minus_shuffle_minimum_bps
        and positive_folds >= thresholds.positive_fold_minimum
        and positive_seeds >= thresholds.positive_seed_minimum
        and drawdown <= thresholds.maximum_drawdown_limit
    )
    return SignalFloorReceipt(
        verdict="PASS_SIGNAL_FLOOR" if passed else "NO_GO_SIGNAL_FLOOR",
        evidence_scope=evidence_scope,
        sample_count=len(samples),
        date_count=len(days),
        native_mean_bps=native_mean_bps,
        diagnostic_9bp_native_mean_bps=(
            (fmean(native_gross) if native_gross else 0.0) * 10_000.0
            - thresholds.diagnostic_round_trip_cost_bps
        ),
        shuffle_mean_bps=shuffle_mean_bps,
        native_minus_shuffle_bps=delta_bps,
        equal_weight_mean_bps=(fmean(equal_returns) if equal_returns else 0.0) * 10_000.0,
        positive_fold_count=positive_folds,
        positive_seed_count=positive_seeds,
        maximum_drawdown=drawdown,
        folds=folds,
    )


def _shuffle_returns(
    by_day: dict[int, list[SignalSample]],
    days: tuple[int, ...],
    seed: int,
    cost: float,
) -> tuple[float, ...]:
    generator = random.Random(seed)
    return tuple(generator.choice(by_day[day]).gross_return - cost for day in days)


def _fold_results(days: tuple[int, ...], returns: tuple[float, ...], fold_count: int) -> tuple[FoldSignalResult, ...]:
    buckets: list[list[float]] = [[] for _ in range(fold_count)]
    for index, value in enumerate(returns):
        fold = min(fold_count - 1, index * fold_count // max(1, len(days)))
        buckets[fold].append(value)
    return tuple(
        FoldSignalResult(fold_id, len(values), (fmean(values) if values else 0.0) * 10_000.0)
        for fold_id, values in enumerate(buckets)
    )


def _maximum_drawdown(returns: tuple[float, ...]) -> float:
    equity = 1.0
    peak = 1.0
    maximum = 0.0
    for value in returns:
        equity *= 1.0 + value
        peak = max(peak, equity)
        maximum = max(maximum, 1.0 - equity / peak)
    return maximum
