"""Type2-D1 research-only decision gates."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Literal

from stom_rl.rl_discovery.d1_contract import D1ArmId
from stom_rl.rl_discovery.gates import RunProfile


@dataclass(frozen=True, slots=True)
class D1Outcome:
    """Economic evaluation for one D1 arm and seed."""

    arm: D1ArmId
    seed: int
    training_timesteps: int
    economic_reward_ratio: float
    initial_decision_accuracy: float
    invalid_action_count: int
    block_count: int
    no_fill_count: int
    dominant_initial_action_rate: float


@dataclass(frozen=True, slots=True)
class D1GateResult:
    """Fail-closed D1 decision without any promotion authority."""

    status: str
    verdict: str
    reasons: tuple[str, ...]
    smoke_pass: bool
    promotion_allowed: Literal[False]
    profitability_claim_allowed: Literal[False]
    fresh_oos: Literal["NOT_RUN_NO_READ"]


def evaluate_d1_gate(
    outcomes: tuple[D1Outcome, ...],
    *,
    profile: RunProfile,
) -> D1GateResult:
    """Evaluate the preregistered D1 reward/action matrix."""

    expected_seeds = {0} if profile is RunProfile.SMOKE else {0, 1, 2}
    by_arm = {
        arm: tuple(outcome for outcome in outcomes if outcome.arm is arm)
        for arm in D1ArmId
    }
    complete = all({outcome.seed for outcome in by_arm[arm]} == expected_seeds for arm in D1ArmId)
    valid = complete and all(
        outcome.invalid_action_count == 0
        and outcome.block_count == 0
        and outcome.no_fill_count == 0
        for outcome in outcomes
    )
    diagnostic = by_arm[D1ArmId.BINARY_DIAGNOSTIC]
    native = by_arm[D1ArmId.BINARY_NATIVE]
    shuffled = by_arm[D1ArmId.BINARY_SHUFFLED]
    diagnostic_pass = bool(diagnostic) and all(
        outcome.initial_decision_accuracy >= 0.90 for outcome in diagnostic
    )
    noncollapsed = bool(native) and all(
        outcome.dominant_initial_action_rate <= 0.90 for outcome in native
    )
    smoke_pass = valid and diagnostic_pass and noncollapsed
    if profile is RunProfile.SMOKE:
        return D1GateResult(
            status="SMOKE_COMPLETE" if complete else "SMOKE_EMPTY",
            verdict="SMOKE_INCOMPLETE",
            reasons=("D1 smoke plumbing passed" if smoke_pass else "D1 smoke gate failed",),
            smoke_pass=smoke_pass,
            promotion_allowed=False,
            profitability_claim_allowed=False,
            fresh_oos="NOT_RUN_NO_READ",
        )
    separated = bool(native) and bool(shuffled) and fmean(
        outcome.economic_reward_ratio for outcome in native
    ) - fmean(outcome.economic_reward_ratio for outcome in shuffled) >= 0.25
    native_pass = bool(native) and all(outcome.economic_reward_ratio >= 0.75 for outcome in native)
    confirmed = smoke_pass and separated and native_pass
    return D1GateResult(
        status="PRIMARY_COMPLETE" if complete else "PRIMARY_INCOMPLETE",
        verdict="D1_ACTION_REWARD_CONFIRMED" if confirmed else "D1_ACTION_REWARD_NOT_CONFIRMED",
        reasons=(
            "binary native reward cleared the shuffled control"
            if confirmed
            else "D1 action/reward confirmation threshold was not satisfied"
        ,),
        smoke_pass=smoke_pass,
        promotion_allowed=False,
        profitability_claim_allowed=False,
        fresh_oos="NOT_RUN_NO_READ",
    )
