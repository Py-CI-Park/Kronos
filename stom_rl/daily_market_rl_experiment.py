"""Preregistered training plan for actual-market offline RL."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Final

from .daily_close_research.offline_data import OfflineTransition
from .daily_market_offline_q import MarketQTrainingResult, train_market_q
from .daily_market_rl_contract import (
    BEHAVIOR_SEEDS,
    MODEL_SEEDS,
    DailyMarketRlContractError,
    MarketAlgorithm,
    MarketTrainingConfig,
    base_cost_config,
    stress_cost_config,
)
from .daily_market_rl_dataset import PreparedMarketData
from .daily_market_rl_evaluation import (
    ConstantMarketPolicy,
    CostAwareMomentumPolicy,
    MarketDecisionPolicy,
    MarketPolicyTrajectory,
    simulate_policy,
)
from .daily_market_rl_trajectory import (
    build_behavior_transitions,
    shuffle_transition_actions,
    shuffle_transition_rewards,
)
from .daily_market_state_dataset import DailyMarketStateDataset
from .daily_market_transition_contract import BinaryAction


@dataclass(frozen=True, slots=True)
class ModelArmPlan:
    """One preregistered algorithm/seed/falsification transform."""

    algorithm: MarketAlgorithm
    seed: int
    shuffle_seed: int


@dataclass(frozen=True, slots=True)
class TrainedModelArm:
    """A trained policy retained in memory until the single TEST read."""

    plan: ModelArmPlan
    training: MarketQTrainingResult
    validation_base: MarketPolicyTrajectory
    validation_stress: MarketPolicyTrajectory


def _identity(
    transitions: tuple[OfflineTransition, ...],
    seed: int,
) -> tuple[OfflineTransition, ...]:
    _ = seed
    return transitions


TransitionTransform = Callable[
    [tuple[OfflineTransition, ...], int],
    tuple[OfflineTransition, ...],
]
TRANSFORMS: Final[dict[MarketAlgorithm, TransitionTransform]] = {
    MarketAlgorithm.DQN: _identity,
    MarketAlgorithm.CQL: _identity,
    MarketAlgorithm.CQL_REWARD_SHUFFLED: lambda rows, seed: shuffle_transition_rewards(rows, seed=seed),
    MarketAlgorithm.CQL_ACTION_SHUFFLED: lambda rows, seed: shuffle_transition_actions(rows, seed=seed),
}


def planned_model_arms() -> tuple[ModelArmPlan, ...]:
    """Expand four algorithm arms across the fixed five seeds."""
    return tuple(
        ModelArmPlan(
            algorithm,
            seed,
            (
                100_000 + seed
                if algorithm is MarketAlgorithm.CQL_REWARD_SHUFFLED
                else 200_000 + seed
                if algorithm is MarketAlgorithm.CQL_ACTION_SHUFFLED
                else 0
            ),
        )
        for algorithm in MarketAlgorithm
        for seed in MODEL_SEEDS
    )


def registered_control_policies(
    state_dataset: DailyMarketStateDataset,
) -> tuple[MarketDecisionPolicy, ...]:
    """Build controls without fitting anything on validation or TEST."""
    return_five = next(
        (row for row in state_dataset.statistics if row.feature == "return_5d"),
        None,
    )
    if return_five is None:
        raise DailyMarketRlContractError("RETURN_5D_TRAIN_STATISTIC_MISSING")
    return (
        ConstantMarketPolicy("NO_TRADE", BinaryAction.CASH),
        ConstantMarketPolicy("ALWAYS_INVEST", BinaryAction.INVEST_TOP10_EQUAL_SLOT),
        CostAwareMomentumPolicy(
            "COST_AWARE_MOMENTUM_RULE",
            return_five.mean,
            return_five.scaling_denominator,
            0.0023,
        ),
    )


def train_model_arms(
    prepared: PreparedMarketData,
    *,
    output_directory: Path,
    on_completed: Callable[[ModelArmPlan, float], None] | None = None,
) -> tuple[int, tuple[TrainedModelArm, ...]]:
    """Train every arm before any historical TEST reward is opened."""
    native = build_behavior_transitions(
        prepared.days,
        prepared.score_scale,
        behavior_seeds=BEHAVIOR_SEEDS,
        cost_config=base_cost_config(),
    )
    trained: list[TrainedModelArm] = []
    for plan in planned_model_arms():
        started = perf_counter()
        transitions = TRANSFORMS[plan.algorithm](native, plan.shuffle_seed)
        config = MarketTrainingConfig.registered(algorithm=plan.algorithm, seed=plan.seed)
        checkpoint = output_directory / "models" / plan.algorithm.value / f"seed-{plan.seed}.kq"
        result = train_market_q(transitions, config, checkpoint_path=checkpoint)
        validation_base = simulate_policy(
            prepared.days,
            prepared.score_scale,
            result.policy,
            split="VALIDATION",
            cost_config=base_cost_config(),
        )
        validation_stress = simulate_policy(
            prepared.days,
            prepared.score_scale,
            result.policy,
            split="VALIDATION",
            cost_config=stress_cost_config(),
        )
        trained.append(TrainedModelArm(plan, result, validation_base, validation_stress))
        if on_completed is not None:
            on_completed(plan, perf_counter() - started)
    return len(native), tuple(trained)


__all__ = [
    "ModelArmPlan",
    "TrainedModelArm",
    "planned_model_arms",
    "registered_control_policies",
    "train_model_arms",
]
