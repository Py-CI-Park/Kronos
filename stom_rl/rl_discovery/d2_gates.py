"""Fail-closed D2 capacity and train-only separation gates."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Literal

from stom_rl.rl_discovery.d2_contract import D2ArmId, D2GateContract
from stom_rl.rl_discovery.d2_training import D2Metrics


@dataclass(frozen=True, slots=True)
class D2Outcome:
    arm: D2ArmId
    episode_count: int
    seed: int
    fit: D2Metrics
    native: D2Metrics
    cost_23bp: D2Metrics


@dataclass(frozen=True, slots=True)
class D2GateResult:
    verdict: str
    maximum_confirmed_episode_count: int
    native_delta_vs_shuffled_at_128: float
    train_only_signal_separation: bool
    promotion_allowed: Literal[False]
    profitability_claim_allowed: Literal[False]
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    reasons: tuple[str, ...]


def evaluate_d2_gate(
    outcomes: tuple[D2Outcome, ...],
    *,
    thresholds: D2GateContract,
) -> D2GateResult:
    """Find the largest scale where PPO-only native and shuffle arms both fit."""

    confirmed: list[int] = []
    for count in (1, 8, 32, 128):
        members = tuple(item for item in outcomes if item.episode_count == count)
        passing = 0
        for seed in (0, 1, 2):
            seed_members = {item.arm: item for item in members if item.seed == seed}
            if set(seed_members) != set(D2ArmId):
                continue
            if all(
                item.fit.accuracy >= thresholds.minimum_fit_accuracy
                and item.fit.reward_ratio >= thresholds.minimum_fit_reward_ratio
                and item.fit.invalid_action_count == 0
                for item in seed_members.values()
            ):
                passing += 1
        if passing / 3 >= thresholds.minimum_primary_passing_seed_fraction:
            confirmed.append(count)
    native_128 = [item.native.reward_ratio for item in outcomes if item.episode_count == 128 and item.arm is D2ArmId.NATIVE]
    shuffled_128 = [item.native.reward_ratio for item in outcomes if item.episode_count == 128 and item.arm is D2ArmId.SHUFFLED]
    delta = fmean(native_128) - fmean(shuffled_128) if native_128 and shuffled_128 else float("-inf")
    separated = delta >= thresholds.minimum_native_delta_vs_shuffled
    maximum = max(confirmed, default=0)
    verdict = (
        "D2_HISTORICAL_CAPACITY_CONFIRMED"
        if maximum == 128 and separated
        else "D2_PARTIAL_CAPACITY_CONFIRMED"
        if maximum >= 8 and separated
        else "D2_HISTORICAL_CAPACITY_NOT_CONFIRMED"
    )
    return D2GateResult(
        verdict=verdict,
        maximum_confirmed_episode_count=maximum,
        native_delta_vs_shuffled_at_128=delta,
        train_only_signal_separation=separated,
        promotion_allowed=False,
        profitability_claim_allowed=False,
        fresh_oos="NOT_RUN_NO_READ",
        reasons=(
            f"largest PPO-only fitted historical scale: {maximum}",
            "23bp results are diagnostic only; Fresh OOS remains unread",
        ),
    )
