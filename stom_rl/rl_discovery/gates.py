"""Type2 discovery outcome gates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean
from typing import Literal


class RunProfile(StrEnum):
    """Supported experiment budgets."""

    SMOKE = "SMOKE"
    PRIMARY = "PRIMARY"


@dataclass(frozen=True, slots=True)
class ArmOutcome:
    """Compact metrics for one arm/seed evaluation."""

    arm: str
    seed: int
    training_timesteps: int
    oracle_reward_ratio: float
    exact_basket_accuracy: float
    invalid_action_count: int
    block_count: int
    no_fill_count: int
    dominant_action_rate: float
    shuffled_reward: bool


@dataclass(frozen=True, slots=True)
class GateResult:
    """Research-only terminal decision for one discovery run."""

    status: str
    verdict: str
    reasons: tuple[str, ...]
    promotion_allowed: bool
    profitability_claim_allowed: bool
    fresh_oos: Literal["NOT_RUN_NO_READ"]


def evaluate_discovery_gate(
    outcomes: tuple[ArmOutcome, ...],
    *,
    profile: RunProfile | str,
) -> GateResult:
    """Evaluate attribution evidence without opening any promotion path."""

    selected_profile = RunProfile(profile)
    if selected_profile is RunProfile.SMOKE:
        status = "SMOKE_COMPLETE" if outcomes else "SMOKE_EMPTY"
        return GateResult(
            status=status,
            verdict="SMOKE_INCOMPLETE",
            reasons=("smoke profile cannot promote", "Fresh OOS remains sealed"),
            promotion_allowed=False,
            profitability_claim_allowed=False,
            fresh_oos="NOT_RUN_NO_READ",
        )

    expected_seeds = {0, 1, 2}
    expected_arms = {
        "A_PPO_ONLY",
        "B_BC_THEN_PPO",
        "C_BC_ONLY",
        "D_SHUFFLED_REWARD_PPO",
    }
    by_arm = {
        arm: tuple(outcome for outcome in outcomes if outcome.arm == arm)
        for arm in expected_arms
    }
    ppo_only = by_arm["A_PPO_ONLY"]
    shuffled = by_arm["D_SHUFFLED_REWARD_PPO"]
    complete_matrix = all({outcome.seed for outcome in by_arm[arm]} == expected_seeds for arm in expected_arms)
    ratios_pass = bool(ppo_only) and all(outcome.oracle_reward_ratio >= 0.9 for outcome in ppo_only)
    shuffled_by_seed = {outcome.seed: outcome for outcome in shuffled}
    per_seed_separated = bool(shuffled) and all(
        outcome.oracle_reward_ratio > shuffled_by_seed[outcome.seed].oracle_reward_ratio
        for outcome in ppo_only
        if outcome.seed in shuffled_by_seed
    )
    mean_separated = bool(ppo_only) and bool(shuffled) and fmean(
        outcome.oracle_reward_ratio for outcome in ppo_only
    ) > fmean(outcome.oracle_reward_ratio for outcome in shuffled)
    valid = all(
        outcome.invalid_action_count == 0
        and outcome.block_count == 0
        and outcome.no_fill_count == 0
        for outcome in outcomes
    )
    noncollapsed = all(outcome.dominant_action_rate < 0.95 for outcome in ppo_only)
    confirmed = complete_matrix and ratios_pass and per_seed_separated and mean_separated and valid and noncollapsed
    reasons = (
        "all PPO-only seeds reached the preregistered memorization threshold",
        "PPO-only exceeded the shuffled-reward control",
        "this confirms training attribution only, not generalization",
    ) if confirmed else (
        "PPO-only attribution threshold was not satisfied",
        "Fresh OOS remains sealed",
    )
    return GateResult(
        status="PRIMARY_COMPLETE" if complete_matrix else "PRIMARY_INCOMPLETE",
        verdict="PPO_ONLY_OVERFIT_CONFIRMED" if confirmed else "PPO_ONLY_OVERFIT_NOT_CONFIRMED",
        reasons=reasons,
        promotion_allowed=False,
        profitability_claim_allowed=False,
        fresh_oos="NOT_RUN_NO_READ",
    )
