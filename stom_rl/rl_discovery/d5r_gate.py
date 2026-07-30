"""Preregistered D5R capacity decision gate."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from stom_rl.rl_discovery.d3_training import D3Metrics


@dataclass(frozen=True, slots=True)
class D5RCapacityOutcome:
    reward_arm: str
    seed: int
    total_steps: int
    native_23bp: D3Metrics


@dataclass(frozen=True, slots=True)
class D5RBaseline:
    seed: int
    accuracy: float
    reward_ratio: float


@dataclass(frozen=True, slots=True)
class D5RCapacityGate:
    verdict: str
    native_accuracy_lift: float
    native_reward_ratio_lift: float
    native_reward_delta_vs_shuffled: float
    improving_seed_fraction: float
    invalid_action_count: int


class D5RGateError(ValueError):
    """D5R capacity evidence is not the exact registered matrix."""


def evaluate_d5r_capacity_gate(
    outcomes: tuple[D5RCapacityOutcome, ...],
    baselines: tuple[D5RBaseline, ...],
) -> D5RCapacityGate:
    expected = {
        (reward_arm, seed, steps)
        for reward_arm in ("NATIVE", "SHUFFLED")
        for seed in range(3)
        for steps in (400_000, 800_000)
    }
    observed = {(row.reward_arm, row.seed, row.total_steps): row for row in outcomes}
    baseline_by_seed = {row.seed: row for row in baselines}
    if (
        set(observed) != expected
        or len(observed) != len(outcomes)
        or set(baseline_by_seed) != set(range(3))
        or len(baselines) != 3
    ):
        raise D5RGateError("D5R capacity gate requires the exact 12-unit matrix and three baselines")
    native_800k = tuple(observed[("NATIVE", seed, 800_000)] for seed in range(3))
    shuffled_800k = tuple(observed[("SHUFFLED", seed, 800_000)] for seed in range(3))
    accuracy_lifts = tuple(
        row.native_23bp.accuracy - baseline_by_seed[row.seed].accuracy for row in native_800k
    )
    reward_lifts = tuple(
        row.native_23bp.reward_ratio - baseline_by_seed[row.seed].reward_ratio for row in native_800k
    )
    accuracy_lift = median(accuracy_lifts)
    reward_lift = median(reward_lifts)
    native_delta = median(row.native_23bp.reward_ratio for row in native_800k) - median(
        row.native_23bp.reward_ratio for row in shuffled_800k
    )
    improving_fraction = sum(
        accuracy > 0 and reward > 0
        for accuracy, reward in zip(accuracy_lifts, reward_lifts, strict=True)
    ) / 3
    invalid_actions = sum(row.native_23bp.invalid_action_count for row in outcomes)
    confirmed = (
        accuracy_lift >= 0.03
        and reward_lift >= 0.02
        and native_delta >= 0.2
        and improving_fraction >= 2 / 3
        and invalid_actions == 0
    )
    return D5RCapacityGate(
        "D5R_CAPACITY_CONFIRMED" if confirmed else "D5R_CAPACITY_NOT_CONFIRMED",
        accuracy_lift,
        reward_lift,
        native_delta,
        improving_fraction,
        invalid_actions,
    )
