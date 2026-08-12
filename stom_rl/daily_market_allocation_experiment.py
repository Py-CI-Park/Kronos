"""Preregistered ten-model plan for validation-only allocation screening."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from .daily_market_allocation_evaluation import simulate_allocation_policy
from .daily_market_allocation_evaluation_contract import AllocationPolicyTrajectory
from .daily_market_allocation_q import AllocationQTrainingResult, train_allocation_q
from .daily_market_allocation_rl_contract import (
    ALLOCATION_MODEL_SEEDS,
    AllocationAlgorithm,
    AllocationTrainingConfig,
)
from .daily_market_allocation_trajectory import build_allocation_behavior_transitions
from .daily_market_rl_contract import (
    BEHAVIOR_SEEDS,
    base_cost_config,
    stress_cost_config,
)
from .daily_market_rl_dataset import PreparedMarketData


@dataclass(frozen=True, slots=True)
class AllocationModelPlan:
    algorithm: AllocationAlgorithm
    seed: int


@dataclass(frozen=True, slots=True)
class TrainedAllocationArm:
    plan: AllocationModelPlan
    training: AllocationQTrainingResult
    validation_base: AllocationPolicyTrajectory
    validation_stress: AllocationPolicyTrajectory


def planned_allocation_arms() -> tuple[AllocationModelPlan, ...]:
    return tuple(
        AllocationModelPlan(algorithm, seed)
        for algorithm in AllocationAlgorithm
        for seed in ALLOCATION_MODEL_SEEDS
    )


def train_allocation_arms(
    prepared: PreparedMarketData,
    *,
    output_directory: Path,
    on_completed: Callable[[AllocationModelPlan, float], None] | None = None,
) -> tuple[int, tuple[TrainedAllocationArm, ...]]:
    """Train and validate all arms without requesting TEST or Fresh OOS rewards."""
    transitions = build_allocation_behavior_transitions(
        prepared.days,
        prepared.score_scale,
        behavior_seeds=BEHAVIOR_SEEDS,
        cost_config=base_cost_config(),
    )
    trained: list[TrainedAllocationArm] = []
    for plan in planned_allocation_arms():
        started = perf_counter()
        config = AllocationTrainingConfig.registered(
            algorithm=plan.algorithm,
            seed=plan.seed,
        )
        checkpoint = (
            output_directory / "models" / plan.algorithm.value / f"seed-{plan.seed}.kq"
        )
        result = train_allocation_q(
            transitions,
            config,
            checkpoint_path=checkpoint,
        )
        validation_base = simulate_allocation_policy(
            prepared.days,
            prepared.score_scale,
            result.policy,
            split="VALIDATION",
            cost_config=base_cost_config(),
        )
        validation_stress = simulate_allocation_policy(
            prepared.days,
            prepared.score_scale,
            result.policy,
            split="VALIDATION",
            cost_config=stress_cost_config(),
        )
        trained.append(
            TrainedAllocationArm(
                plan,
                result,
                validation_base,
                validation_stress,
            )
        )
        if on_completed is not None:
            on_completed(plan, perf_counter() - started)
    return len(transitions), tuple(trained)


__all__ = [
    "AllocationModelPlan",
    "TrainedAllocationArm",
    "planned_allocation_arms",
    "train_allocation_arms",
]
