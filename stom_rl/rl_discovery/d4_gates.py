"""Fail-closed supervised-ceiling and RL algorithm gates for D4."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Literal

from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d4_contract import D4AlgorithmArmId, D4GateContract, D4RewardArmId


class D4GateEvidenceError(ValueError):
    """Primary evidence does not match the frozen D4 matrix."""


@dataclass(frozen=True, slots=True)
class D4Outcome:
    algorithm_arm: D4AlgorithmArmId
    reward_arm: D4RewardArmId
    seed: int
    fit: D3Metrics
    native: D3Metrics
    cost_23bp: D3Metrics


@dataclass(frozen=True, slots=True)
class D4GateResult:
    verdict: str
    supervised_ceiling_confirmed: bool
    confirmed_rl_arms: tuple[D4AlgorithmArmId, ...]
    best_rl_arm: D4AlgorithmArmId
    native_delta_vs_shuffled: tuple[tuple[D4AlgorithmArmId, float], ...]
    best_rl_gap_to_supervised_ceiling: float
    promotion_allowed: Literal[False]
    profitability_claim_allowed: Literal[False]
    fresh_oos: Literal["NOT_RUN_NO_READ"]


def evaluate_d4_gate(outcomes: tuple[D4Outcome, ...], *, thresholds: D4GateContract) -> D4GateResult:
    """Separate representation ceiling from genuine RL algorithm confirmation."""

    expected = {
        (algorithm, reward, seed)
        for algorithm in D4AlgorithmArmId
        for reward in D4RewardArmId
        for seed in (0, 1, 2)
    }
    observed = {(item.algorithm_arm, item.reward_arm, item.seed) for item in outcomes}
    if len(outcomes) != len(expected) or observed != expected:
        raise D4GateEvidenceError("D4 Primary gate requires the exact unique 24-unit matrix")

    native_means: dict[D4AlgorithmArmId, float] = {}
    deltas: list[tuple[D4AlgorithmArmId, float]] = []
    pass_fractions: dict[tuple[D4AlgorithmArmId, D4RewardArmId], float] = {}
    for arm in D4AlgorithmArmId:
        members = tuple(item for item in outcomes if item.algorithm_arm is arm)
        for reward in D4RewardArmId:
            pass_fractions[(arm, reward)] = _passing_fraction(members, reward, thresholds)
        native = fmean(item.native.reward_ratio for item in members if item.reward_arm is D4RewardArmId.NATIVE)
        shuffled = fmean(item.native.reward_ratio for item in members if item.reward_arm is D4RewardArmId.SHUFFLED)
        native_means[arm] = native
        deltas.append((arm, native - shuffled))

    ceiling = D4AlgorithmArmId.SUPERVISED_CEILING
    ceiling_delta = dict(deltas)[ceiling]
    ceiling_confirmed = (
        pass_fractions[(ceiling, D4RewardArmId.NATIVE)] >= thresholds.minimum_passing_seed_fraction
        and ceiling_delta >= thresholds.minimum_native_delta_vs_shuffled
    )
    rl_arms = tuple(arm for arm in D4AlgorithmArmId if arm is not ceiling)
    confirmed: list[D4AlgorithmArmId] = []
    for arm in rl_arms:
        gap = native_means[ceiling] - native_means[arm]
        gap_ok = ceiling_confirmed and gap <= thresholds.maximum_rl_gap_to_supervised_ceiling
        if (
            pass_fractions[(arm, D4RewardArmId.NATIVE)] >= thresholds.minimum_passing_seed_fraction
            and pass_fractions[(arm, D4RewardArmId.SHUFFLED)] >= thresholds.minimum_passing_seed_fraction
            and dict(deltas)[arm] >= thresholds.minimum_native_delta_vs_shuffled
            and gap_ok
        ):
            confirmed.append(arm)
    best = max(rl_arms, key=lambda arm: native_means[arm])
    best_gap = native_means[ceiling] - native_means[best]
    verdict = (
        "D4_ALGORITHM_OBJECTIVE_CONFIRMED"
        if ceiling_confirmed and confirmed
        else "D4_RL_OPTIMIZATION_NOT_CONFIRMED"
        if ceiling_confirmed
        else "D4_REPRESENTATION_CEILING_NOT_CONFIRMED"
    )
    return D4GateResult(
        verdict=verdict,
        supervised_ceiling_confirmed=ceiling_confirmed,
        confirmed_rl_arms=tuple(confirmed),
        best_rl_arm=best,
        native_delta_vs_shuffled=tuple(deltas),
        best_rl_gap_to_supervised_ceiling=best_gap,
        promotion_allowed=False,
        profitability_claim_allowed=False,
        fresh_oos="NOT_RUN_NO_READ",
    )


def _passing_fraction(
    members: tuple[D4Outcome, ...],
    reward_arm: D4RewardArmId,
    thresholds: D4GateContract,
) -> float:
    selected = tuple(item for item in members if item.reward_arm is reward_arm)
    passing = sum(
        item.fit.accuracy >= thresholds.minimum_fit_accuracy
        and item.fit.reward_ratio >= thresholds.minimum_fit_reward_ratio
        and item.fit.invalid_action_count == 0
        for item in selected
    )
    return passing / len(selected)
