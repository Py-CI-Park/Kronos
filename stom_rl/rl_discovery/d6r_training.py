"""Deterministic fold-specific DQN training for D6R."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
from typing import Protocol, Self, assert_never

import numpy as np
from numpy.typing import NDArray

from stom_rl.rl_discovery.d3_env import D3Episode, D3Representation
from stom_rl.rl_discovery.d6r_env import D6RTradePenaltyEnv
from stom_rl.rl_discovery.d6r_gate import D6RProfileId
from stom_rl.rl_discovery.torch_runtime import prepare_torch_runtime


class D6RTrainingError(ValueError):
    """A D6R training request violates the registered schedule."""


class D6RTrainable(Protocol):
    def learn(self, *, total_timesteps: int, reset_num_timesteps: bool, progress_bar: bool) -> Self: ...
    def predict(self, observation: NDArray[np.float32], *, deterministic: bool) -> tuple[NDArray[np.generic], tuple[NDArray[np.float32], ...] | None]: ...
    def save(self, path: Path) -> None: ...


@dataclass(frozen=True, slots=True)
class D6RLineage:
    model: D6RTrainable
    trained_steps: int


def training_penalty_bp(profile: D6RProfileId) -> int:
    match profile:
        case "COST_ONLY":
            return 0
        case "TURNOVER_10BP":
            return 10
    assert_never(profile)


def start_d6r_lineage(
    episodes: tuple[D3Episode, ...],
    *,
    representation: D3Representation,
    seed: int,
    cost_bp: int,
    additional_trade_penalty_bp: int,
) -> D6RLineage:
    _ = prepare_torch_runtime()
    import torch
    from stable_baselines3.dqn.dqn import DQN
    from stable_baselines3.common.vec_env import DummyVecEnv

    random.seed(seed)
    np.random.seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    vector = DummyVecEnv(
        [
            lambda: D6RTradePenaltyEnv(
                episodes,
                representation=representation,
                cost_bp=cost_bp,
                additional_trade_penalty_bp=additional_trade_penalty_bp,
            )
        ]
    )
    model: D6RTrainable = DQN(
        "MlpPolicy",
        vector,
        seed=seed,
        device="cpu",
        gamma=1.0,
        learning_rate=3e-4,
        buffer_size=200_000,
        learning_starts=128,
        batch_size=64,
        train_freq=4,
        gradient_steps=1,
        target_update_interval=10_000,
        exploration_fraction=0.2,
        exploration_final_eps=0.02,
        policy_kwargs={"net_arch": [256, 128]},
        verbose=0,
    )
    return D6RLineage(model, 0)


def advance_d6r_lineage(lineage: D6RLineage, *, target_steps: int) -> D6RLineage:
    if target_steps <= lineage.trained_steps:
        raise D6RTrainingError("D6R target steps must advance the registered lineage")
    _ = lineage.model.learn(
        total_timesteps=target_steps - lineage.trained_steps,
        reset_num_timesteps=False,
        progress_bar=False,
    )
    return D6RLineage(lineage.model, target_steps)
