"""Exact 70-unit decision gate for D6R2."""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from typing import Literal

from stom_rl.rl_discovery.d3_training import D3Metrics

D6R2Algorithm = Literal["DQN_GAMMA_0_CONTEXTUAL", "DQN_GAMMA_1_SEQUENCE_CONTROL", "RIDGE_REWARD_CEILING"]
D6R2RewardArm = Literal["NATIVE", "SHUFFLED"]


@dataclass(frozen=True, slots=True)
class D6R2UnitOutcome:
    algorithm: D6R2Algorithm
    reward_arm: D6R2RewardArm
    seed: int
    fold_id: int
    evaluation_23bp: D3Metrics
    maximum_drawdown_23bp: float
    normalizer_evaluation_row_count: int


@dataclass(frozen=True, slots=True)
class D6R2GateThresholds:
    minimum_accuracy: float
    minimum_reward_ratio: float
    minimum_lift_vs_gamma1: float
    minimum_delta_vs_shuffled: float
    minimum_positive_fold_fraction: float
    minimum_positive_seed_fraction: float
    maximum_trade_rate: float
    maximum_drawdown: float
    minimum_ridge_reward_ratio: float
    minimum_ridge_delta_vs_shuffled: float
    minimum_ridge_positive_fold_fraction: float

    @classmethod
    def registered(cls) -> D6R2GateThresholds:
        return cls(0.2, 0.0, 0.05, 0.1, 0.8, 2 / 3, 0.65, 0.25, 0.0, 0.1, 0.8)


@dataclass(frozen=True, slots=True)
class D6R2GateResult:
    verdict: str
    gamma0_native_median_accuracy: float
    gamma0_native_median_reward_ratio: float
    gamma0_lift_vs_gamma1: float
    gamma0_delta_vs_shuffled: float
    gamma0_positive_fold_fraction: float
    gamma0_positive_seed_fraction: float
    gamma0_native_median_trade_rate: float
    gamma0_native_median_drawdown: float
    ridge_native_median_reward_ratio: float
    ridge_delta_vs_shuffled: float
    ridge_positive_fold_fraction: float
    invalid_action_count: int
    normalizer_evaluation_row_count: int
    passed_gate_count: int
    total_gate_count: int


class D6R2GateError(ValueError):
    """D6R2 outcomes do not match the frozen matrix."""


def evaluate_d6r2_gate(outcomes: tuple[D6R2UnitOutcome, ...], *, thresholds: D6R2GateThresholds) -> D6R2GateResult:
    expected = {
        (algorithm, arm, seed, fold)
        for algorithm in ("DQN_GAMMA_0_CONTEXTUAL", "DQN_GAMMA_1_SEQUENCE_CONTROL")
        for arm in ("NATIVE", "SHUFFLED")
        for seed in range(3)
        for fold in range(5)
    } | {
        ("RIDGE_REWARD_CEILING", arm, 0, fold)
        for arm in ("NATIVE", "SHUFFLED")
        for fold in range(5)
    }
    indexed = {(row.algorithm, row.reward_arm, row.seed, row.fold_id): row for row in outcomes}
    if len(outcomes) != 70 or set(indexed) != expected:
        raise D6R2GateError("D6R2 gate requires the exact 70-unit matrix")
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
        raise D6R2GateError("D6R2 metrics must be finite")
    gamma0_native = _rows(indexed, "DQN_GAMMA_0_CONTEXTUAL", "NATIVE", range(3))
    gamma0_shuffled = _rows(indexed, "DQN_GAMMA_0_CONTEXTUAL", "SHUFFLED", range(3))
    gamma1_native = _rows(indexed, "DQN_GAMMA_1_SEQUENCE_CONTROL", "NATIVE", range(3))
    ridge_native = _rows(indexed, "RIDGE_REWARD_CEILING", "NATIVE", (0,))
    ridge_shuffled = _rows(indexed, "RIDGE_REWARD_CEILING", "SHUFFLED", (0,))
    accuracy = median(row.evaluation_23bp.accuracy for row in gamma0_native)
    gamma0_ratio = median(row.evaluation_23bp.reward_ratio for row in gamma0_native)
    lift = gamma0_ratio - median(row.evaluation_23bp.reward_ratio for row in gamma1_native)
    delta = gamma0_ratio - median(row.evaluation_23bp.reward_ratio for row in gamma0_shuffled)
    positive_folds = _positive_fold_fraction(indexed, "DQN_GAMMA_0_CONTEXTUAL", range(3))
    positive_seeds = sum(
        median(indexed[("DQN_GAMMA_0_CONTEXTUAL", "NATIVE", seed, fold)].evaluation_23bp.total_reward for fold in range(5)) > 0
        for seed in range(3)
    ) / 3
    trade_rate = median(row.evaluation_23bp.trade_rate for row in gamma0_native)
    drawdown = median(row.maximum_drawdown_23bp for row in gamma0_native)
    ridge_ratio = median(row.evaluation_23bp.reward_ratio for row in ridge_native)
    ridge_delta = ridge_ratio - median(row.evaluation_23bp.reward_ratio for row in ridge_shuffled)
    ridge_folds = _positive_fold_fraction(indexed, "RIDGE_REWARD_CEILING", (0,))
    invalid = sum(row.evaluation_23bp.invalid_action_count for row in outcomes)
    eval_rows = sum(row.normalizer_evaluation_row_count for row in outcomes)
    passed = (
        accuracy >= thresholds.minimum_accuracy,
        gamma0_ratio >= thresholds.minimum_reward_ratio,
        lift >= thresholds.minimum_lift_vs_gamma1,
        delta >= thresholds.minimum_delta_vs_shuffled,
        positive_folds >= thresholds.minimum_positive_fold_fraction,
        positive_seeds >= thresholds.minimum_positive_seed_fraction,
        trade_rate <= thresholds.maximum_trade_rate,
        drawdown <= thresholds.maximum_drawdown,
        ridge_ratio >= thresholds.minimum_ridge_reward_ratio,
        ridge_delta >= thresholds.minimum_ridge_delta_vs_shuffled,
        ridge_folds >= thresholds.minimum_ridge_positive_fold_fraction,
        invalid == 0,
        eval_rows == 0,
    )
    if all(passed):
        verdict = "D6R2_CONTEXTUAL_CANDIDATE"
    elif all(passed[8:11]):
        verdict = "D6R2_RL_NOT_CONFIRMED_SIGNAL_FLOOR_PRESENT"
    else:
        verdict = "D6R2_TOP5_SIGNAL_FLOOR_NOT_CONFIRMED"
    return D6R2GateResult(
        verdict, accuracy, gamma0_ratio, lift, delta, positive_folds, positive_seeds,
        trade_rate, drawdown, ridge_ratio, ridge_delta, ridge_folds, invalid, eval_rows,
        sum(passed), len(passed),
    )


def _rows(indexed: dict[tuple[str, str, int, int], D6R2UnitOutcome], algorithm: str, arm: str, seeds: range | tuple[int, ...]) -> tuple[D6R2UnitOutcome, ...]:
    return tuple(indexed[(algorithm, arm, seed, fold)] for seed in seeds for fold in range(5))


def _positive_fold_fraction(indexed: dict[tuple[str, str, int, int], D6R2UnitOutcome], algorithm: str, seeds: range | tuple[int, ...]) -> float:
    return sum(
        median(indexed[(algorithm, "NATIVE", seed, fold)].evaluation_23bp.total_reward for seed in seeds) > 0
        for fold in range(5)
    ) / 5

