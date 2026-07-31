"""Exact six-unit gate for D6 reused validation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from typing import Literal

from stom_rl.rl_discovery.d3_training import D3Metrics


class D6GateEvidenceError(ValueError):
    """D6 evidence does not match the registered six-unit matrix."""


@dataclass(frozen=True, slots=True)
class D6Evaluation:
    reward_arm: Literal["NATIVE", "SHUFFLED"]
    seed: int
    metrics: D3Metrics
    maximum_drawdown: float


@dataclass(frozen=True, slots=True)
class D6GateThresholds:
    minimum_native_median_accuracy: float
    minimum_native_median_reward_ratio: float
    minimum_native_median_total_reward: float
    minimum_native_reward_delta_vs_shuffled: float
    minimum_passing_native_seed_fraction: float
    maximum_native_median_reward_drawdown: float
    zero_invalid_actions: bool


@dataclass(frozen=True, slots=True)
class D6GateResult:
    verdict: Literal["D6_REUSED_VALIDATION_CONFIRMED", "D6_REUSED_VALIDATION_NOT_CONFIRMED"]
    native_median_accuracy: float
    native_median_reward_ratio: float
    native_median_total_reward: float
    shuffled_median_reward_ratio: float
    native_reward_delta_vs_shuffled: float
    native_passing_seed_fraction: float
    native_median_reward_drawdown: float
    invalid_action_count: int
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    promotion_allowed: Literal[False]
    profitability_claim_allowed: Literal[False]


def evaluate_d6_gate(
    evaluations: tuple[D6Evaluation, ...],
    *,
    thresholds: D6GateThresholds,
) -> D6GateResult:
    expected = {(arm, seed) for arm in ("NATIVE", "SHUFFLED") for seed in range(3)}
    observed = {(row.reward_arm, row.seed) for row in evaluations}
    if len(evaluations) != len(expected) or observed != expected:
        raise D6GateEvidenceError("D6 requires the exact unique six-unit matrix")
    native = tuple(row for row in evaluations if row.reward_arm == "NATIVE")
    shuffled = tuple(row for row in evaluations if row.reward_arm == "SHUFFLED")
    native_accuracy = median(row.metrics.accuracy for row in native)
    native_ratio = median(row.metrics.reward_ratio for row in native)
    native_reward = median(row.metrics.total_reward for row in native)
    shuffled_ratio = median(row.metrics.reward_ratio for row in shuffled)
    delta = native_ratio - shuffled_ratio
    native_drawdown = median(row.maximum_drawdown for row in native)
    invalid = sum(row.metrics.invalid_action_count for row in evaluations)
    passing = sum(
        _meets(row.metrics.accuracy, thresholds.minimum_native_median_accuracy)
        and _meets(row.metrics.total_reward, thresholds.minimum_native_median_total_reward)
        and _at_most(row.maximum_drawdown, thresholds.maximum_native_median_reward_drawdown)
        and row.metrics.invalid_action_count == 0
        for row in native
    ) / len(native)
    confirmed = (
        _meets(native_accuracy, thresholds.minimum_native_median_accuracy)
        and _meets(native_ratio, thresholds.minimum_native_median_reward_ratio)
        and _meets(native_reward, thresholds.minimum_native_median_total_reward)
        and _meets(delta, thresholds.minimum_native_reward_delta_vs_shuffled)
        and _meets(passing, thresholds.minimum_passing_native_seed_fraction)
        and _at_most(native_drawdown, thresholds.maximum_native_median_reward_drawdown)
        and (not thresholds.zero_invalid_actions or invalid == 0)
    )
    verdict = (
        "D6_REUSED_VALIDATION_CONFIRMED"
        if confirmed
        else "D6_REUSED_VALIDATION_NOT_CONFIRMED"
    )
    return D6GateResult(
        verdict,
        native_accuracy,
        native_ratio,
        native_reward,
        shuffled_ratio,
        delta,
        passing,
        native_drawdown,
        invalid,
        "NOT_RUN_NO_READ",
        False,
        False,
    )


def _meets(value: float, threshold: float) -> bool:
    return value >= threshold or math.isclose(value, threshold, rel_tol=0, abs_tol=1e-12)


def _at_most(value: float, threshold: float) -> bool:
    return value <= threshold or math.isclose(value, threshold, rel_tol=0, abs_tol=1e-12)
