"""Action-count-agnostic deterministic NumPy Q optimization kernel."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .daily_close_research.offline_data import OfflineTransition
from .daily_market_q_network import AdamOptimizer, MarketQNetwork, q_loss_and_gradients
from .daily_market_rl_contract import DailyMarketRlContractError


@dataclass(frozen=True, slots=True)
class QOptimizationPlan:
    seed: int
    input_dimension: int
    action_count: int
    hidden_dimensions: tuple[int, int]
    learning_rate: float
    discount: float
    cql_alpha: float
    reward_scale: float
    batch_size: int
    gradient_steps: int
    target_update_interval: int


@dataclass(frozen=True, slots=True)
class QOptimizationResult:
    network: MarketQNetwork
    losses: tuple[float, ...]


def _validate_transitions(
    transitions: tuple[OfflineTransition, ...],
    plan: QOptimizationPlan,
) -> None:
    if not transitions:
        raise DailyMarketRlContractError("TRAINING_TRANSITIONS_MISSING")
    for row in transitions:
        if (
            len(row.state) != plan.input_dimension
            or len(row.next_state) != plan.input_dimension
        ):
            raise DailyMarketRlContractError(
                "TRAINING_STATE_DIMENSION_MISMATCH",
                str(row.sequence),
            )
        if not 0 <= row.action < plan.action_count or not math.isfinite(row.reward):
            raise DailyMarketRlContractError(
                "TRAINING_TRANSITION_INVALID",
                str(row.sequence),
            )


def optimize_q_network(
    transitions: tuple[OfflineTransition, ...],
    plan: QOptimizationPlan,
) -> QOptimizationResult:
    """Train one fixed-step Double-DQN/CQL network deterministically."""
    _validate_transitions(transitions, plan)
    generator = np.random.default_rng(plan.seed)
    network = MarketQNetwork.initialize(
        plan.input_dimension,
        plan.hidden_dimensions,
        plan.action_count,
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
    for step in range(plan.gradient_steps):
        indices = generator.integers(0, len(transitions), size=plan.batch_size)
        next_online = network.predict(next_states[indices])
        next_actions = np.asarray(np.argmax(next_online, axis=1), dtype=np.int64)
        next_target = target.predict(next_states[indices])
        selected_next = next_target[np.arange(plan.batch_size), next_actions]
        target_values = (
            rewards[indices] * plan.reward_scale
            + plan.discount * (1.0 - done[indices]) * selected_next
        )
        loss, gradients = q_loss_and_gradients(
            network,
            states[indices],
            actions[indices],
            target_values,
            cql_alpha=plan.cql_alpha,
        )
        optimizer.step(network, gradients, plan.learning_rate)
        losses.append(loss)
        if (step + 1) % plan.target_update_interval == 0:
            target.copy_from(network)
    return QOptimizationResult(network, tuple(losses))


__all__ = ["QOptimizationPlan", "QOptimizationResult", "optimize_q_network"]
