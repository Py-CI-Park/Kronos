"""DQN gamma controls and a non-RL ridge reward ceiling for D6R2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
from typing import Protocol, Self

import numpy as np
from numpy.typing import NDArray

from stom_rl.rl_discovery.d3_env import D3Episode, D3Representation, HistoricalTopKEnv
from stom_rl.rl_discovery.torch_runtime import prepare_torch_runtime


class D6R2Trainable(Protocol):
    def learn(self, *, total_timesteps: int, reset_num_timesteps: bool, progress_bar: bool) -> Self: ...
    def predict(self, observation: NDArray[np.float32], *, deterministic: bool) -> tuple[NDArray[np.generic], tuple[NDArray[np.float32], ...] | None]: ...
    def save(self, path: Path) -> None: ...


@dataclass(frozen=True, slots=True)
class D6R2DqnPolicy:
    model: D6R2Trainable

    def predict(self, observation: NDArray[np.float32], *, deterministic: bool, action_masks: NDArray[np.bool_]) -> tuple[NDArray[np.int64], None]:
        _ = action_masks
        action, _state = self.model.predict(observation, deterministic=deterministic)
        return np.asarray(action, dtype=np.int64), None

    def save(self, path: Path) -> None:
        self.model.save(path)


@dataclass(frozen=True, slots=True)
class RidgeRewardPolicy:
    coefficients: NDArray[np.float64]

    def predict(self, observation: NDArray[np.float32], *, deterministic: bool, action_masks: NDArray[np.bool_]) -> tuple[NDArray[np.int64], None]:
        _ = deterministic
        vector = np.concatenate((np.ones(1, dtype=np.float64), np.asarray(observation, dtype=np.float64).reshape(-1)))
        scores = vector @ self.coefficients
        scores = np.where(action_masks, scores, -np.inf)
        return np.asarray(int(np.argmax(scores)), dtype=np.int64), None

    def save(self, path: Path) -> None:
        with path.with_suffix(".npz").open("wb") as stream:
            np.savez_compressed(stream, coefficients=self.coefficients)


class D6R2TrainingError(ValueError):
    """A training request falls outside the preregistered D6R2 matrix."""


def train_dqn_policy(
    episodes: tuple[D3Episode, ...],
    *,
    representation: D3Representation,
    seed: int,
    gamma: float,
    training_steps: int,
    cost_bp: int,
) -> D6R2DqnPolicy:
    """Train the preregistered SB3 DQN with only gamma varying."""

    if gamma not in {0.0, 1.0} or training_steps < 1:
        raise D6R2TrainingError("D6R2 DQN requires registered gamma and positive steps")
    _ = prepare_torch_runtime()
    import torch
    from stable_baselines3 import DQN
    from stable_baselines3.common.vec_env import DummyVecEnv

    random.seed(seed)
    np.random.seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    vector = DummyVecEnv([lambda: HistoricalTopKEnv(episodes, representation=representation, cost_bp=cost_bp)])
    model: D6R2Trainable = DQN(
        "MlpPolicy",
        vector,
        seed=seed,
        device="cpu",
        gamma=gamma,
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
    _ = model.learn(total_timesteps=training_steps, reset_num_timesteps=True, progress_bar=False)
    return D6R2DqnPolicy(model)


def train_ridge_reward_policy(
    episodes: tuple[D3Episode, ...],
    *,
    representation: D3Representation,
    cost_bp: int,
    alpha: float,
) -> RidgeRewardPolicy:
    """Fit six counterfactual 23bp action rewards as a supervised ceiling."""

    observations = np.asarray([representation.observation(episode) for episode in episodes], dtype=np.float64)
    design = np.column_stack((np.ones(len(observations), dtype=np.float64), observations))
    targets = np.zeros((len(episodes), representation.action_count), dtype=np.float64)
    for row_index, episode in enumerate(episodes):
        targets[row_index, 1:] = tuple(candidate[2] - cost_bp / 10_000 for candidate in episode.candidates)
    penalty = alpha * np.eye(design.shape[1], dtype=np.float64)
    penalty[0, 0] = 0.0
    coefficients = np.asarray(
        np.linalg.solve(design.T @ design + penalty, design.T @ targets),
        dtype=np.float64,
    )
    return RidgeRewardPolicy(coefficients)
