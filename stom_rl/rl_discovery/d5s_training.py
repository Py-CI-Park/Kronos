"""Deterministic lower-rate DQN lineages for D5S."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
from typing import Protocol, Self

from numpy.typing import NDArray
import numpy as np

from stom_rl.rl_discovery.d3_env import D3Episode, D3Representation, HistoricalTopKEnv
from stom_rl.rl_discovery.torch_runtime import prepare_torch_runtime


class D5STrainingError(ValueError):
    """A D5S lineage request violates the registered schedule."""


class D5STrainable(Protocol):
    def learn(self, *, total_timesteps: int, reset_num_timesteps: bool, progress_bar: bool) -> Self: ...
    def predict(self, observation: NDArray[np.float32], *, deterministic: bool) -> tuple[NDArray[np.generic], tuple[NDArray[np.float32], ...] | None]: ...
    def save(self, path: Path) -> None: ...


@dataclass(frozen=True, slots=True)
class D5SLineage:
    model: D5STrainable
    trained_steps: int


def start_d5s_lineage(
    episodes: tuple[D3Episode, ...],
    *,
    representation: D3Representation,
    seed: int,
    cost_bp: int,
) -> D5SLineage:
    _ = prepare_torch_runtime()
    import torch
    from stable_baselines3 import DQN
    from stable_baselines3.common.vec_env import DummyVecEnv

    random.seed(seed)
    np.random.seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    vector = DummyVecEnv(
        [lambda: HistoricalTopKEnv(episodes, representation=representation, cost_bp=cost_bp)]
    )
    model: D5STrainable = DQN(
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
    return D5SLineage(model, 0)


def advance_d5s_lineage(lineage: D5SLineage, *, target_steps: int) -> D5SLineage:
    if target_steps <= lineage.trained_steps:
        raise D5STrainingError("D5S target steps must advance the registered lineage")
    _ = lineage.model.learn(
        total_timesteps=target_steps - lineage.trained_steps,
        reset_num_timesteps=False,
        progress_bar=False,
    )
    return D5SLineage(lineage.model, target_steps)
