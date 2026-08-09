"""Four-action policies backed by the shared deterministic Q optimizer."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from .daily_close_research.offline_data import OfflineTransition
from .daily_market_allocation_contract import AllocationAction
from .daily_market_allocation_rl_contract import (
    AllocationAlgorithm,
    AllocationTrainingConfig,
)
from .daily_market_q_checkpoint import load_network, save_network
from .daily_market_q_network import MarketQNetwork
from .daily_market_q_training import QOptimizationPlan, optimize_q_network
from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_rl_dataset import MarketDay


@dataclass(frozen=True, slots=True)
class AllocationQPolicy:
    """Greedy four-action policy backed by numeric-only weights."""

    name: str
    network: MarketQNetwork
    input_dimension: int
    policy_kind: Literal["RL"] = "RL"

    def q_values(
        self, observation: tuple[float, ...]
    ) -> tuple[float, float, float, float]:
        if len(observation) != self.input_dimension:
            raise DailyMarketRlContractError(
                "ALLOCATION_POLICY_STATE_DIMENSION_MISMATCH",
                str(len(observation)),
            )
        values = self.network.predict(np.asarray((observation,), dtype=np.float64))
        return (
            float(values.item(0, 0)),
            float(values.item(0, 1)),
            float(values.item(0, 2)),
            float(values.item(0, 3)),
        )

    def greedy_action(self, observation: tuple[float, ...]) -> AllocationAction:
        values = self.q_values(observation)
        return AllocationAction(max(range(4), key=values.__getitem__))

    def action(
        self, observation: tuple[float, ...], day: MarketDay
    ) -> AllocationAction:
        _ = day
        return self.greedy_action(observation)


@dataclass(frozen=True, slots=True)
class AllocationQTrainingResult:
    algorithm: AllocationAlgorithm
    seed: int
    policy: AllocationQPolicy
    losses: tuple[float, ...]
    checkpoint_path: Path | None
    checkpoint_sha256: str | None


def _optimization_plan(config: AllocationTrainingConfig) -> QOptimizationPlan:
    return QOptimizationPlan(
        seed=config.seed,
        input_dimension=config.input_dimension,
        action_count=config.action_count,
        hidden_dimensions=config.hidden_dimensions,
        learning_rate=config.learning_rate,
        discount=config.discount,
        cql_alpha=config.cql_alpha,
        reward_scale=config.reward_scale,
        batch_size=config.batch_size,
        gradient_steps=config.gradient_steps,
        target_update_interval=config.target_update_interval,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def train_allocation_q(
    transitions: tuple[OfflineTransition, ...],
    config: AllocationTrainingConfig,
    *,
    checkpoint_path: Path | None = None,
) -> AllocationQTrainingResult:
    optimized = optimize_q_network(transitions, _optimization_plan(config))
    policy = AllocationQPolicy(
        config.algorithm.value,
        optimized.network,
        config.input_dimension,
    )
    checkpoint_hash: str | None = None
    if checkpoint_path is not None:
        save_network(optimized.network, checkpoint_path)
        checkpoint_hash = _sha256(checkpoint_path)
    return AllocationQTrainingResult(
        config.algorithm,
        config.seed,
        policy,
        optimized.losses,
        checkpoint_path,
        checkpoint_hash,
    )


def load_allocation_q(
    path: Path,
    config: AllocationTrainingConfig,
) -> AllocationQPolicy:
    expected_shapes = (
        (config.input_dimension, config.hidden_dimensions[0]),
        (config.hidden_dimensions[0],),
        (config.hidden_dimensions[0], config.hidden_dimensions[1]),
        (config.hidden_dimensions[1],),
        (config.hidden_dimensions[1], config.action_count),
        (config.action_count,),
    )
    network = load_network(path, expected_shapes)
    return AllocationQPolicy(config.algorithm.value, network, config.input_dimension)


__all__ = [
    "AllocationQPolicy",
    "AllocationQTrainingResult",
    "load_allocation_q",
    "train_allocation_q",
]
