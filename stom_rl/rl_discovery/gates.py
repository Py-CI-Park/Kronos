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

    ppo_only = tuple(outcome for outcome in outcomes if outcome.arm == "A_PPO_ONLY")
    shuffled = tuple(outcome for outcome in outcomes if outcome.arm == "D_SHUFFLED_REWARD_PPO")
    ppo_seeds = {outcome.seed for outcome in ppo_only}
    shuffled_seeds = {outcome.seed for outcome in shuffled}
    complete_controls = ppo_seeds == {0, 1, 2} and shuffled_seeds == {0, 1, 2}
    ratios_pass = bool(ppo_only) and all(outcome.oracle_reward_ratio >= 0.9 for outcome in ppo_only)
    separated = bool(shuffled) and fmean(outcome.oracle_reward_ratio for outcome in ppo_only) > fmean(
        outcome.oracle_reward_ratio for outcome in shuffled
    )
    confirmed = complete_controls and ratios_pass and separated
    reasons = (
        "all PPO-only seeds reached the preregistered memorization threshold",
        "PPO-only exceeded the shuffled-reward control",
        "this confirms training attribution only, not generalization",
    ) if confirmed else (
        "PPO-only attribution threshold was not satisfied",
        "Fresh OOS remains sealed",
    )
    return GateResult(
        status="PRIMARY_COMPLETE" if complete_controls else "PRIMARY_INCOMPLETE",
        verdict="PPO_ONLY_OVERFIT_CONFIRMED" if confirmed else "PPO_ONLY_OVERFIT_NOT_CONFIRMED",
        reasons=reasons,
        promotion_allowed=False,
        profitability_claim_allowed=False,
        fresh_oos="NOT_RUN_NO_READ",
    )
