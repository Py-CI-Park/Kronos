"""Deterministic NumPy DQN and CQL training for the actual-market lane."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from .daily_close_research.offline_data import OfflineTransition
from .daily_market_q_checkpoint import load_network, save_network
from .daily_market_q_network import MarketQNetwork
from .daily_market_q_training import QOptimizationPlan, optimize_q_network
from .daily_market_rl_contract import (
    DailyMarketRlContractError,
    MarketAlgorithm,
    MarketTrainingConfig,
)
from .daily_market_rl_dataset import MarketDay
from .daily_market_transition_contract import BinaryAction


@dataclass(frozen=True, slots=True)
class MarketQPolicy:
    """Greedy binary policy backed by a typed NumPy Q-network."""

    name: str
    network: MarketQNetwork
    input_dimension: int
    policy_kind: Literal["RL"] = "RL"

    def q_values(self, observation: tuple[float, ...]) -> tuple[float, float]:
        if len(observation) != self.input_dimension:
            raise DailyMarketRlContractError(
                "POLICY_STATE_DIMENSION_MISMATCH",
                str(len(observation)),
            )
        values = self.network.predict(np.asarray((observation,), dtype=np.float64))
        return float(values.item(0, 0)), float(values.item(0, 1))

    def greedy_action(self, observation: tuple[float, ...]) -> BinaryAction:
        cash, invest = self.q_values(observation)
        return (
            BinaryAction.INVEST_TOP10_EQUAL_SLOT if invest > cash else BinaryAction.CASH
        )

    def action(self, observation: tuple[float, ...], day: MarketDay) -> BinaryAction:
        _ = day
        return self.greedy_action(observation)


@dataclass(frozen=True, slots=True)
class MarketQTrainingResult:
    """In-memory policy and optimization evidence for one seed."""

    algorithm: MarketAlgorithm
    seed: int
    policy: MarketQPolicy
    losses: tuple[float, ...]
    checkpoint_path: Path | None
    checkpoint_sha256: str | None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def train_market_q(
    transitions: tuple[OfflineTransition, ...],
    config: MarketTrainingConfig,
    *,
    checkpoint_path: Path | None = None,
) -> MarketQTrainingResult:
    """Train one fixed-step Double-DQN/CQL arm deterministically."""
    optimized = optimize_q_network(
        transitions,
        QOptimizationPlan(
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
        ),
    )
    policy = MarketQPolicy(
        config.algorithm.value,
        optimized.network,
        config.input_dimension,
    )
    checkpoint_hash: str | None = None
    if checkpoint_path is not None:
        save_network(optimized.network, checkpoint_path)
        checkpoint_hash = _sha256(checkpoint_path)
    return MarketQTrainingResult(
        config.algorithm,
        config.seed,
        policy,
        optimized.losses,
        checkpoint_path,
        checkpoint_hash,
    )


def load_market_q(path: Path, config: MarketTrainingConfig) -> MarketQPolicy:
    """Load only numeric arrays into the preregistered architecture."""
    expected_shapes = (
        (config.input_dimension, config.hidden_dimensions[0]),
        (config.hidden_dimensions[0],),
        (config.hidden_dimensions[0], config.hidden_dimensions[1]),
        (config.hidden_dimensions[1],),
        (config.hidden_dimensions[1], config.action_count),
        (config.action_count,),
    )
    network = load_network(path, expected_shapes)
    return MarketQPolicy(config.algorithm.value, network, config.input_dimension)


__all__ = [
    "MarketQPolicy",
    "MarketQTrainingResult",
    "load_market_q",
    "train_market_q",
]
