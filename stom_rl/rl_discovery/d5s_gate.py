"""Preregistered global checkpoint selection and D5S stability gate."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Final, Literal

from stom_rl.rl_discovery.d3_training import D3Metrics


@dataclass(frozen=True, slots=True)
class D5SCheckpointOutcome:
    reward_arm: Literal["NATIVE", "SHUFFLED"]
    seed: int
    total_steps: int
    native_23bp: D3Metrics


@dataclass(frozen=True, slots=True)
class D5SBaseline:
    seed: int
    accuracy: float
    reward_ratio: float


@dataclass(frozen=True, slots=True)
class D5SStabilityGate:
    verdict: str
    selected_steps: int
    selected_native_median_accuracy: float
    selected_native_median_reward_ratio: float
    selected_native_reward_delta_vs_shuffled: float
    accuracy_degradation_at_400k: float
    reward_ratio_degradation_at_400k: float
    preserved_native_seed_fraction: float
    invalid_action_count: int


class D5SGateError(ValueError):
    """D5S evidence is not the exact preregistered matrix."""


CHECKPOINTS: Final = (50_000, 100_000, 150_000, 200_000, 300_000, 400_000)


def select_global_checkpoint(outcomes: tuple[D5SCheckpointOutcome, ...]) -> int:
    expected = {
        (arm, seed, steps)
        for arm in ("NATIVE", "SHUFFLED")
        for seed in range(3)
        for steps in CHECKPOINTS
    }
    observed = {(row.reward_arm, row.seed, row.total_steps) for row in outcomes}
    if observed != expected or len(observed) != len(outcomes):
        raise D5SGateError("D5S selection requires the exact 36-unit matrix")
    native = tuple(row for row in outcomes if row.reward_arm == "NATIVE")
    return max(
        CHECKPOINTS,
        key=lambda steps: (
            median(row.native_23bp.reward_ratio for row in native if row.total_steps == steps),
            median(row.native_23bp.accuracy for row in native if row.total_steps == steps),
            -steps,
        ),
    )


def evaluate_d5s_stability_gate(
    outcomes: tuple[D5SCheckpointOutcome, ...],
    baselines: tuple[D5SBaseline, ...],
) -> D5SStabilityGate:
    selected_steps = select_global_checkpoint(outcomes)
    baseline_by_seed = {row.seed: row for row in baselines}
    if len(baselines) != 3 or set(baseline_by_seed) != set(range(3)):
        raise D5SGateError("D5S stability gate requires three unique D5 baselines")
    indexed = {(row.reward_arm, row.seed, row.total_steps): row for row in outcomes}
    selected_native = tuple(indexed[("NATIVE", seed, selected_steps)] for seed in range(3))
    selected_shuffled = tuple(indexed[("SHUFFLED", seed, selected_steps)] for seed in range(3))
    final_native = tuple(indexed[("NATIVE", seed, 400_000)] for seed in range(3))
    selected_accuracy = median(row.native_23bp.accuracy for row in selected_native)
    selected_reward = median(row.native_23bp.reward_ratio for row in selected_native)
    final_accuracy = median(row.native_23bp.accuracy for row in final_native)
    final_reward = median(row.native_23bp.reward_ratio for row in final_native)
    native_delta = selected_reward - median(
        row.native_23bp.reward_ratio for row in selected_shuffled
    )
    accuracy_degradation = max(0.0, selected_accuracy - final_accuracy)
    reward_degradation = max(0.0, selected_reward - final_reward)
    preserved_fraction = sum(
        row.native_23bp.accuracy >= baseline_by_seed[row.seed].accuracy
        and row.native_23bp.reward_ratio >= baseline_by_seed[row.seed].reward_ratio
        for row in selected_native
    ) / 3
    invalid_actions = sum(row.native_23bp.invalid_action_count for row in outcomes)
    confirmed = (
        selected_accuracy >= 0.7120418848167539
        and selected_reward >= 0.8727793884825973
        and native_delta >= 0.2
        and accuracy_degradation <= 0.05
        and reward_degradation <= 0.05
        and preserved_fraction >= 2 / 3
        and invalid_actions == 0
    )
    return D5SStabilityGate(
        "D5S_STABILITY_CONFIRMED" if confirmed else "D5S_STABILITY_NOT_CONFIRMED",
        selected_steps,
        selected_accuracy,
        selected_reward,
        native_delta,
        accuracy_degradation,
        reward_degradation,
        preserved_fraction,
        invalid_actions,
    )
