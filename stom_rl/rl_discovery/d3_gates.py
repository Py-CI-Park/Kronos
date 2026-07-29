"""Fail-closed representation, action, and budget gates for D3."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Literal

from stom_rl.rl_discovery.d3_contract import D3GateContract, D3PolicyArmId, D3RewardArmId
from stom_rl.rl_discovery.d3_training import D3Metrics


class D3GateEvidenceError(ValueError):
    """The Primary evidence does not match the preregistered D3 matrix."""


@dataclass(frozen=True, slots=True)
class D3Outcome:
    policy_arm: D3PolicyArmId
    reward_arm: D3RewardArmId
    seed: int
    fit: D3Metrics
    native: D3Metrics
    cost_23bp: D3Metrics


@dataclass(frozen=True, slots=True)
class D3GateResult:
    verdict: str
    confirmed_policy_arms: tuple[D3PolicyArmId, ...]
    best_policy_arm: D3PolicyArmId
    native_delta_vs_shuffled: tuple[tuple[D3PolicyArmId, float], ...]
    budget_4x_native_lift: float
    promotion_allowed: Literal[False]
    profitability_claim_allowed: Literal[False]
    fresh_oos: Literal["NOT_RUN_NO_READ"]


def evaluate_d3_gate(outcomes: tuple[D3Outcome, ...], *, thresholds: D3GateContract) -> D3GateResult:
    """Confirm arms only when native and shuffled fit plus separation all pass."""

    expected_units = {
        (policy_arm, reward_arm, seed)
        for policy_arm in D3PolicyArmId
        for reward_arm in D3RewardArmId
        for seed in (0, 1, 2)
    }
    observed_units = {(item.policy_arm, item.reward_arm, item.seed) for item in outcomes}
    if len(outcomes) != len(expected_units) or observed_units != expected_units:
        raise D3GateEvidenceError("D3 Primary gate requires the exact unique 24-unit matrix")
    confirmed: list[D3PolicyArmId] = []
    deltas: list[tuple[D3PolicyArmId, float]] = []
    native_means: dict[D3PolicyArmId, float] = {}
    for arm in D3PolicyArmId:
        members = tuple(item for item in outcomes if item.policy_arm is arm)
        native_fit = _passing_seed_fraction(members, D3RewardArmId.NATIVE, thresholds)
        shuffled_fit = _passing_seed_fraction(members, D3RewardArmId.SHUFFLED, thresholds)
        native_scores = [item.native.reward_ratio for item in members if item.reward_arm is D3RewardArmId.NATIVE]
        shuffled_scores = [item.native.reward_ratio for item in members if item.reward_arm is D3RewardArmId.SHUFFLED]
        native_mean = fmean(native_scores) if native_scores else float("-inf")
        shuffled_mean = fmean(shuffled_scores) if shuffled_scores else float("inf")
        delta = native_mean - shuffled_mean
        native_means[arm] = native_mean
        deltas.append((arm, delta))
        if native_fit >= thresholds.minimum_passing_seed_fraction and shuffled_fit >= thresholds.minimum_passing_seed_fraction and delta >= thresholds.minimum_native_delta_vs_shuffled:
            confirmed.append(arm)
    best = max(D3PolicyArmId, key=lambda arm: native_means[arm])
    budget_lift = native_means[D3PolicyArmId.TOP5_CONTEXT_4X] - native_means[D3PolicyArmId.TOP5_CONTEXT_1X]
    return D3GateResult(
        verdict="D3_REPRESENTATION_ACTION_CONFIRMED" if confirmed else "D3_REPRESENTATION_ACTION_NOT_CONFIRMED",
        confirmed_policy_arms=tuple(confirmed),
        best_policy_arm=best,
        native_delta_vs_shuffled=tuple(deltas),
        budget_4x_native_lift=budget_lift,
        promotion_allowed=False,
        profitability_claim_allowed=False,
        fresh_oos="NOT_RUN_NO_READ",
    )


def _passing_seed_fraction(members: tuple[D3Outcome, ...], reward_arm: D3RewardArmId, thresholds: D3GateContract) -> float:
    selected = tuple(item for item in members if item.reward_arm is reward_arm)
    passing = sum(
        item.fit.accuracy >= thresholds.minimum_fit_accuracy
        and item.fit.reward_ratio >= thresholds.minimum_fit_reward_ratio
        and item.fit.invalid_action_count == 0
        for item in selected
    )
    return passing / len(selected)
