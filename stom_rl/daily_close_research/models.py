"""Small discrete offline DQN and CQL models for auditable research."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import cast

import torch
from torch import Tensor, nn

from .offline_data import OfflineTransition


class OfflineAlgorithm(str, Enum):
    DQN = "DQN"
    CQL = "CQL"


class _QNetwork(nn.Module):
    def __init__(self, state_dimension: int, action_count: int, hidden_dimension: int) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(state_dimension, hidden_dimension),
            nn.Tanh(),
            nn.Linear(hidden_dimension, action_count),
        )

    def forward(self, states: Tensor) -> Tensor:
        return self.layers(states)


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    algorithm: OfflineAlgorithm
    seed: int
    epochs: int
    state_dimension: int
    action_count: int
    hidden_dimension: int
    learning_rate: float
    discount: float
    cql_alpha: float

    @classmethod
    def registered(
        cls,
        *,
        algorithm: OfflineAlgorithm,
        seed: int,
        epochs: int,
    ) -> TrainingConfig:
        return cls(algorithm, seed, epochs, 2, 2, 16, 0.01, 0.95, 0.01)


@dataclass(frozen=True, slots=True)
class QPolicy:
    network: _QNetwork
    state_dimension: int
    action_count: int
    hidden_dimension: int

    def q_values(self, state: tuple[float, ...]) -> tuple[float, ...]:
        if len(state) != self.state_dimension:
            raise ValueError("state dimension mismatch")
        with torch.no_grad():
            values = self.network(torch.tensor((state,), dtype=torch.float32))[0]
        return tuple(float(value) for value in values.tolist())

    def action(self, state: tuple[float, ...]) -> int:
        values = self.q_values(state)
        return max(range(len(values)), key=lambda index: (values[index], -index))


@dataclass(frozen=True, slots=True)
class TrainingResult:
    algorithm: OfflineAlgorithm
    seed: int
    model: QPolicy
    losses: tuple[float, ...]
    output: Path | None


def train_offline_q(
    transitions: tuple[OfflineTransition, ...],
    config: TrainingConfig,
    *,
    output: Path | None = None,
) -> TrainingResult:
    if not transitions or config.epochs < 1:
        raise ValueError("training requires transitions and positive epochs")
    torch.manual_seed(config.seed)
    network = _QNetwork(config.state_dimension, config.action_count, config.hidden_dimension)
    optimizer = torch.optim.Adam(network.parameters(), lr=config.learning_rate)
    states = torch.tensor([item.state for item in transitions], dtype=torch.float32)
    actions = torch.tensor([item.action for item in transitions], dtype=torch.int64)
    rewards = torch.tensor([item.reward for item in transitions], dtype=torch.float32)
    next_states = torch.tensor([item.next_state for item in transitions], dtype=torch.float32)
    done = torch.tensor([item.done for item in transitions], dtype=torch.float32)
    losses: list[float] = []
    for _ in range(config.epochs):
        q_all = network(states)
        q_observed = q_all.gather(1, actions.unsqueeze(1)).squeeze(1)
        with torch.no_grad():
            target = rewards + config.discount * (1.0 - done) * network(next_states).max(dim=1).values
        temporal_loss = nn.functional.mse_loss(q_observed, target)
        conservative_loss = torch.logsumexp(q_all, dim=1).mean() - q_observed.mean()
        alpha = config.cql_alpha if config.algorithm is OfflineAlgorithm.CQL else 0.0
        loss = temporal_loss + alpha * conservative_loss
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach()))
    policy = QPolicy(network, config.state_dimension, config.action_count, config.hidden_dimension)
    if output is not None:
        _save_q_model(policy, config.algorithm, output)
    return TrainingResult(config.algorithm, config.seed, policy, tuple(losses), output)


def load_q_model(path: Path) -> QPolicy:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(payload, dict):
        raise ValueError("invalid Q model payload")
    state_dimension = int(payload["state_dimension"])
    action_count = int(payload["action_count"])
    hidden_dimension = int(payload["hidden_dimension"])
    network = _QNetwork(state_dimension, action_count, hidden_dimension)
    state = cast(dict[str, Tensor], payload["state_dict"])
    network.load_state_dict(state)
    network.eval()
    return QPolicy(network, state_dimension, action_count, hidden_dimension)


def _save_q_model(policy: QPolicy, algorithm: OfflineAlgorithm, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    torch.save(
        {
            "algorithm": algorithm.value,
            "state_dimension": policy.state_dimension,
            "action_count": policy.action_count,
            "hidden_dimension": policy.hidden_dimension,
            "state_dict": policy.network.state_dict(),
        },
        temporary,
    )
    temporary.replace(output)
