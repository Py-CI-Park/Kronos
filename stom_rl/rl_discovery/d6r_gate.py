"""Preregistered D6R fold, control, churn, and drawdown gate."""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from typing import Literal

from stom_rl.rl_discovery.d3_training import D3Metrics

D6RProfileId = Literal["COST_ONLY", "TURNOVER_10BP"]
D6RRewardArm = Literal["NATIVE", "SHUFFLED"]


@dataclass(frozen=True, slots=True)
class D6RUnitOutcome:
    profile: D6RProfileId
    reward_arm: D6RRewardArm
    seed: int
    fold_id: int
    evaluation_23bp: D3Metrics
    evaluation_0bp: D3Metrics
    maximum_drawdown_23bp: float


@dataclass(frozen=True, slots=True)
class D6RGateThresholds:
    minimum_native_median_accuracy: float
    minimum_native_median_reward_ratio: float
    minimum_native_median_total_reward: float
    minimum_native_reward_delta_vs_shuffled: float
    minimum_positive_fold_fraction: float
    minimum_positive_seed_fraction: float
    maximum_native_median_trade_rate: float
    minimum_trade_rate_reduction_vs_cost_only: float
    maximum_native_median_reward_drawdown: float
    zero_invalid_actions: bool


@dataclass(frozen=True, slots=True)
class D6RGateResult:
    verdict: str
    native_median_accuracy: float
    native_median_reward_ratio: float
    native_median_total_reward: float
    native_reward_delta_vs_shuffled: float
    positive_fold_fraction: float
    positive_seed_fraction: float
    native_median_trade_rate: float
    trade_rate_reduction_vs_cost_only: float
    native_median_reward_drawdown: float
    invalid_action_count: int
    passed_gate_count: int
    total_gate_count: int


class D6RGateError(ValueError):
    """D6R outcomes do not form the exact preregistered matrix."""


def evaluate_d6r_gate(
    outcomes: tuple[D6RUnitOutcome, ...],
    *,
    thresholds: D6RGateThresholds,
) -> D6RGateResult:
    expected = {
        (profile, arm, seed, fold_id)
        for profile in ("COST_ONLY", "TURNOVER_10BP")
        for arm in ("NATIVE", "SHUFFLED")
        for seed in range(3)
        for fold_id in range(5)
    }
    indexed = {
        (row.profile, row.reward_arm, row.seed, row.fold_id): row
        for row in outcomes
    }
    if len(outcomes) != 60 or set(indexed) != expected:
        raise D6RGateError("D6R gate requires the exact 60-unit matrix")
    values = tuple(
        value
        for row in outcomes
        for value in (
            row.evaluation_23bp.accuracy,
            row.evaluation_23bp.reward_ratio,
            row.evaluation_23bp.total_reward,
            row.evaluation_23bp.trade_rate,
            row.maximum_drawdown_23bp,
        )
    )
    if not all(math.isfinite(value) for value in values):
        raise D6RGateError("D6R gate metrics must be finite")
    primary_native = tuple(
        indexed[("TURNOVER_10BP", "NATIVE", seed, fold_id)]
        for seed in range(3)
        for fold_id in range(5)
    )
    primary_shuffled = tuple(
        indexed[("TURNOVER_10BP", "SHUFFLED", seed, fold_id)]
        for seed in range(3)
        for fold_id in range(5)
    )
    cost_native = tuple(
        indexed[("COST_ONLY", "NATIVE", seed, fold_id)]
        for seed in range(3)
        for fold_id in range(5)
    )
    accuracy = median(row.evaluation_23bp.accuracy for row in primary_native)
    reward_ratio = median(row.evaluation_23bp.reward_ratio for row in primary_native)
    total_reward = median(row.evaluation_23bp.total_reward for row in primary_native)
    reward_delta = reward_ratio - median(
        row.evaluation_23bp.reward_ratio for row in primary_shuffled
    )
    positive_folds = sum(
        median(
            indexed[("TURNOVER_10BP", "NATIVE", seed, fold_id)].evaluation_23bp.total_reward
            for seed in range(3)
        )
        > 0.0
        for fold_id in range(5)
    ) / 5
    positive_seeds = sum(
        median(
            indexed[("TURNOVER_10BP", "NATIVE", seed, fold_id)].evaluation_23bp.total_reward
            for fold_id in range(5)
        )
        > 0.0
        for seed in range(3)
    ) / 3
    primary_trade_rate = median(
        row.evaluation_23bp.trade_rate for row in primary_native
    )
    trade_reduction = median(
        row.evaluation_23bp.trade_rate for row in cost_native
    ) - primary_trade_rate
    drawdown = median(row.maximum_drawdown_23bp for row in primary_native)
    invalid_actions = sum(row.evaluation_23bp.invalid_action_count for row in outcomes)
    passed = (
        accuracy >= thresholds.minimum_native_median_accuracy,
        reward_ratio >= thresholds.minimum_native_median_reward_ratio,
        total_reward >= thresholds.minimum_native_median_total_reward,
        reward_delta >= thresholds.minimum_native_reward_delta_vs_shuffled,
        positive_folds >= thresholds.minimum_positive_fold_fraction,
        positive_seeds >= thresholds.minimum_positive_seed_fraction,
        primary_trade_rate <= thresholds.maximum_native_median_trade_rate,
        trade_reduction >= thresholds.minimum_trade_rate_reduction_vs_cost_only,
        drawdown <= thresholds.maximum_native_median_reward_drawdown,
        invalid_actions == 0 if thresholds.zero_invalid_actions else True,
    )
    passed_count = sum(passed)
    verdict = (
        "D6R_TRAIN_FALSIFICATION_CANDIDATE"
        if passed_count == len(passed)
        else "D6R_TRAIN_FALSIFICATION_NOT_CONFIRMED"
    )
    return D6RGateResult(
        verdict,
        accuracy,
        reward_ratio,
        total_reward,
        reward_delta,
        positive_folds,
        positive_seeds,
        primary_trade_rate,
        trade_reduction,
        drawdown,
        invalid_actions,
        passed_count,
        len(passed),
    )
