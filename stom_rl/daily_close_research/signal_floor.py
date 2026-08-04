"""Expanding-window ridge signal floor with shuffled controls."""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from statistics import fmean

import numpy as np
from numpy.typing import NDArray

from .features import RankSample


@dataclass(frozen=True, slots=True)
class SignalFloorConfig:
    round_trip_cost_percent: float
    validation_fold_count: int
    positive_fold_minimum: int
    native_minus_shuffle_minimum_percent: float
    ridge_penalty: float

    @classmethod
    def registered(cls, *, round_trip_cost_percent: float) -> SignalFloorConfig:
        return cls(round_trip_cost_percent, 4, 3, 0.05, 1.0)


@dataclass(frozen=True, slots=True)
class RankFoldResult:
    fold_id: int
    train_date_count: int
    validation_date_count: int
    net_mean_percent: float


@dataclass(frozen=True, slots=True)
class RankSignalReceipt:
    verdict: str
    sample_count: int
    date_count: int
    validation_fold_count: int
    positive_fold_count: int
    net_mean_percent: float
    shuffle_mean_percent: float
    native_minus_shuffle_percent: float
    folds: tuple[RankFoldResult, ...]


def evaluate_rank_signal(
    samples: tuple[RankSample, ...],
    config: SignalFloorConfig,
    *,
    shuffle_seeds: tuple[int, ...],
) -> RankSignalReceipt:
    if config.round_trip_cost_percent < 0 or config.validation_fold_count < 1:
        raise ValueError("invalid signal-floor configuration")
    by_day: dict[int, list[RankSample]] = defaultdict(list)
    for sample in samples:
        by_day[sample.day].append(sample)
    days = tuple(sorted(by_day))
    buckets = _date_buckets(days, config.validation_fold_count + 1)
    native_returns: list[float] = []
    fold_results: list[RankFoldResult] = []
    validation_rows: list[tuple[RankSample, ...]] = []
    cost_rate = config.round_trip_cost_percent / 100.0
    for fold_id in range(1, len(buckets)):
        train_days = tuple(day for bucket in buckets[:fold_id] for day in bucket)
        validation_days = buckets[fold_id]
        weights = _fit_ridge(tuple(row for day in train_days for row in by_day[day]), config.ridge_penalty)
        fold_returns: list[float] = []
        for day in validation_days:
            candidates = tuple(by_day[day])
            selected = max(candidates, key=lambda row: (_predict(row, weights), row.code))
            fold_returns.append(selected.forward_return - cost_rate)
            validation_rows.append(candidates)
        native_returns.extend(fold_returns)
        fold_results.append(
            RankFoldResult(
                fold_id=fold_id,
                train_date_count=len(train_days),
                validation_date_count=len(validation_days),
                net_mean_percent=_mean(fold_returns) * 100.0,
            )
        )
    shuffle_returns = tuple(
        _shuffle_mean(validation_rows, seed, cost_rate)
        for seed in shuffle_seeds
    )
    native_mean = _mean(native_returns) * 100.0
    shuffle_mean = _mean(shuffle_returns) * 100.0
    delta = native_mean - shuffle_mean
    positive_folds = sum(result.net_mean_percent > 0 for result in fold_results)
    passed = (
        bool(native_returns)
        and native_mean > 0
        and positive_folds >= config.positive_fold_minimum
        and delta >= config.native_minus_shuffle_minimum_percent
    )
    return RankSignalReceipt(
        verdict="PASS_SIGNAL_FLOOR" if passed else "NO_GO_SIGNAL_FLOOR",
        sample_count=len(samples),
        date_count=len(days),
        validation_fold_count=len(fold_results),
        positive_fold_count=positive_folds,
        net_mean_percent=native_mean,
        shuffle_mean_percent=shuffle_mean,
        native_minus_shuffle_percent=delta,
        folds=tuple(fold_results),
    )


def _fit_ridge(rows: tuple[RankSample, ...], penalty: float) -> tuple[float, ...]:
    if not rows:
        return ()
    features: NDArray[np.float64] = np.asarray([row.features for row in rows], dtype=np.float64)
    targets: NDArray[np.float64] = np.asarray([row.forward_return for row in rows], dtype=np.float64)
    means = features.mean(axis=0)
    scales = features.std(axis=0)
    scales[scales == 0] = 1.0
    standardized = (features - means) / scales
    design = np.column_stack((np.ones(len(rows)), standardized))
    regularizer = np.eye(design.shape[1], dtype=np.float64) * penalty
    regularizer[0, 0] = 0.0
    coefficients = np.linalg.solve(design.T @ design + regularizer, design.T @ targets)
    return tuple(float(value) for value in np.concatenate((means, scales, coefficients)))


def _predict(row: RankSample, packed: tuple[float, ...]) -> float:
    if not packed:
        return 0.0
    width = len(row.features)
    means = np.asarray(packed[:width])
    scales = np.asarray(packed[width : width * 2])
    coefficients = np.asarray(packed[width * 2 :])
    values = (np.asarray(row.features) - means) / scales
    return float(coefficients[0] + values @ coefficients[1:])


def _date_buckets(days: tuple[int, ...], count: int) -> tuple[tuple[int, ...], ...]:
    buckets: list[list[int]] = [[] for _ in range(count)]
    for index, day in enumerate(days):
        bucket = min(count - 1, index * count // max(1, len(days)))
        buckets[bucket].append(day)
    return tuple(tuple(bucket) for bucket in buckets)


def _shuffle_mean(rows: list[tuple[RankSample, ...]], seed: int, cost_rate: float) -> float:
    generator = random.Random(seed)
    return _mean([generator.choice(candidates).forward_return - cost_rate for candidates in rows if candidates])


def _mean(values: list[float] | tuple[float, ...]) -> float:
    return fmean(values) if values else 0.0

