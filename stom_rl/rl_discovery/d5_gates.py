"""Exact-matrix D5 full-train cost and control gate."""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import fmean
from typing import Literal

from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d4_contract import D4RewardArmId
from stom_rl.rl_discovery.d5_contract import D5GateContract


class D5GateEvidenceError(ValueError):
    """D5 evidence does not match the registered ten-unit matrix."""


@dataclass(frozen=True, slots=True)
class D5Outcome:
    reward_arm: D4RewardArmId
    seed: int
    fit_23bp: D3Metrics
    native_23bp: D3Metrics
    native_0bp: D3Metrics


@dataclass(frozen=True, slots=True)
class D5GateResult:
    verdict: str
    native_passing_seed_fraction: float
    shuffled_passing_seed_fraction: float
    native_delta_vs_shuffled: float
    promotion_allowed: Literal[False]
    profitability_claim_allowed: Literal[False]
    reused_validation: Literal["NOT_RUN_NO_READ"]
    fresh_oos: Literal["NOT_RUN_NO_READ"]


def evaluate_d5_gate(outcomes: tuple[D5Outcome, ...], *, thresholds: D5GateContract) -> D5GateResult:
    """Evaluate the frozen D5 matrix without opening validation data."""

    expected = {(reward, seed) for reward in D4RewardArmId for seed in range(5)}
    observed = {(item.reward_arm, item.seed) for item in outcomes}
    if len(outcomes) != len(expected) or observed != expected:
        raise D5GateEvidenceError("D5 requires the exact unique ten-unit matrix")
    native_fraction = _passing_fraction(outcomes, D4RewardArmId.NATIVE, thresholds)
    shuffled_fraction = _passing_fraction(outcomes, D4RewardArmId.SHUFFLED, thresholds)
    native_mean = fmean(item.native_23bp.reward_ratio for item in outcomes if item.reward_arm is D4RewardArmId.NATIVE)
    shuffled_native = fmean(item.native_23bp.reward_ratio for item in outcomes if item.reward_arm is D4RewardArmId.SHUFFLED)
    delta = native_mean - shuffled_native
    confirmed = (
        _meets(native_fraction, thresholds.minimum_passing_seed_fraction)
        and _meets(shuffled_fraction, thresholds.minimum_passing_seed_fraction)
        and _meets(delta, thresholds.minimum_native_delta_vs_shuffled)
    )
    return D5GateResult("D5_FULL_TRAIN_COST_CONFIRMED" if confirmed else "D5_FULL_TRAIN_COST_NOT_CONFIRMED", native_fraction, shuffled_fraction, delta, False, False, "NOT_RUN_NO_READ", "NOT_RUN_NO_READ")


def _passing_fraction(outcomes: tuple[D5Outcome, ...], reward: D4RewardArmId, thresholds: D5GateContract) -> float:
    selected = tuple(item for item in outcomes if item.reward_arm is reward)
    passing = sum(item.fit_23bp.accuracy >= thresholds.minimum_fit_accuracy and item.fit_23bp.reward_ratio >= thresholds.minimum_fit_reward_ratio and item.fit_23bp.invalid_action_count == 0 for item in selected)
    return passing / len(selected)


def _meets(value: float, threshold: float) -> bool:
    return value >= threshold or math.isclose(value, threshold, rel_tol=0, abs_tol=1e-12)
