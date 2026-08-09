"""Deterministic NumPy DQN and CQL training for the actual-market lane."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from .daily_close_research.offline_data import OfflineTransition
from .daily_market_q_checkpoint import load_network, save_network
from .daily_market_q_network import (
    AdamOptimizer,
    MarketQNetwork,
    q_loss_and_gradients,
)
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
        return BinaryAction.INVEST_TOP10_EQUAL_SLOT if invest > cash else BinaryAction.CASH

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


def _validate_transitions(
    transitions: tuple[OfflineTransition, ...],
    config: MarketTrainingConfig,
) -> None:
    if not transitions:
        raise DailyMarketRlContractError("TRAINING_TRANSITIONS_MISSING")
    for row in transitions:
        if len(row.state) != config.input_dimension or len(row.next_state) != config.input_dimension:
            raise DailyMarketRlContractError(
                "TRAINING_STATE_DIMENSION_MISMATCH",
                str(row.sequence),
            )
        if row.action not in (0, 1) or not math.isfinite(row.reward):
            raise DailyMarketRlContractError("TRAINING_TRANSITION_INVALID", str(row.sequence))


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
    _validate_transitions(transitions, config)
    generator = np.random.default_rng(config.seed)
    network = MarketQNetwork.initialize(
        config.input_dimension,
        config.hidden_dimensions,
        config.action_count,
        generator,
    )
    target = network.clone()
    optimizer = AdamOptimizer(network)
    states = np.asarray([row.state for row in transitions], dtype=np.float64)
    actions = np.asarray([row.action for row in transitions], dtype=np.int64)
    rewards = np.asarray([row.reward for row in transitions], dtype=np.float64)
    next_states = np.asarray([row.next_state for row in transitions], dtype=np.float64)
    done = np.asarray([row.done for row in transitions], dtype=np.float64)
    losses: list[float] = []
    for step in range(config.gradient_steps):
        indices = generator.integers(0, len(transitions), size=config.batch_size)
        next_online = network.predict(next_states[indices])
        next_actions = np.asarray(np.argmax(next_online, axis=1), dtype=np.int64)
        next_target = target.predict(next_states[indices])
        selected_next = next_target[np.arange(config.batch_size), next_actions]
        target_values = (
            rewards[indices] * config.reward_scale
            + config.discount * (1.0 - done[indices]) * selected_next
        )
        loss, gradients = q_loss_and_gradients(
            network,
            states[indices],
            actions[indices],
            target_values,
            cql_alpha=config.cql_alpha,
        )
        optimizer.step(network, gradients, config.learning_rate)
        losses.append(loss)
        if (step + 1) % config.target_update_interval == 0:
            target.copy_from(network)
    policy = MarketQPolicy(config.algorithm.value, network, config.input_dimension)
    checkpoint_hash: str | None = None
    if checkpoint_path is not None:
        save_network(network, checkpoint_path)
        checkpoint_hash = _sha256(checkpoint_path)
    return MarketQTrainingResult(
        config.algorithm,
        config.seed,
        policy,
        tuple(losses),
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
