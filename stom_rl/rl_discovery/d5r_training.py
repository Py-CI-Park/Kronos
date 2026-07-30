"""Deterministic uninterrupted DQN lineages for D5R capacity checkpoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
from typing import Protocol, Self

import numpy as np
from numpy.typing import NDArray

from stom_rl.rl_discovery.d3_env import D3Episode, D3Representation, HistoricalTopKEnv
from stom_rl.rl_discovery.torch_runtime import prepare_torch_runtime


class D5RTrainable(Protocol):
    def learn(
        self,
        *,
        total_timesteps: int,
        reset_num_timesteps: bool,
        progress_bar: bool,
    ) -> Self: ...

    def predict(
        self,
        observation: NDArray[np.float32],
        *,
        deterministic: bool,
    ) -> tuple[NDArray[np.generic], tuple[NDArray[np.float32], ...] | None]: ...

    def save(self, path: Path) -> None: ...


@dataclass(frozen=True, slots=True)
class D5RLineage:
    model: D5RTrainable
    trained_steps: int


class D5RTrainingError(ValueError):
    """A D5R capacity lineage request violates the registered schedule."""


def start_d5r_lineage(
    episodes: tuple[D3Episode, ...],
    *,
    representation: D3Representation,
    seed: int,
    cost_bp: int,
) -> D5RLineage:
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
    model: D5RTrainable = DQN(
        "MlpPolicy",
        vector,
        seed=seed,
        device="cpu",
        gamma=1.0,
        learning_rate=1e-3,
        buffer_size=200_000,
        learning_starts=128,
        batch_size=64,
        train_freq=4,
        gradient_steps=1,
        policy_kwargs={"net_arch": [256, 128]},
        verbose=0,
    )
    return D5RLineage(model, 0)


def advance_d5r_lineage(lineage: D5RLineage, *, target_steps: int) -> D5RLineage:
    if target_steps <= lineage.trained_steps:
        raise D5RTrainingError("D5R target steps must advance the registered lineage")
    additional_steps = target_steps - lineage.trained_steps
    _ = lineage.model.learn(
        total_timesteps=additional_steps,
        reset_num_timesteps=False,
        progress_bar=False,
    )
    return D5RLineage(lineage.model, target_steps)
