"""MaskablePPO training and replay metrics for the D3 ablation matrix."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import random
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from stom_rl.rl_discovery.d3_env import D3Episode, D3Representation, HistoricalTopKEnv
from stom_rl.rl_discovery.torch_runtime import prepare_torch_runtime


class D3Predictor(Protocol):
    def predict(self, observation: NDArray[np.float32], *, deterministic: bool, action_masks: NDArray[np.bool_]) -> tuple[NDArray[np.int64], None]: ...
    def save(self, path: Path) -> None: ...


class D3Normalizer(Protocol):
    def save(self, path: Path) -> None: ...


@dataclass(frozen=True, slots=True)
class D3TrainingConfig:
    seed: int
    timesteps: int
    n_steps: int = 128
    batch_size: int = 64
    n_epochs: int = 10
    learning_rate: float = 1e-3


@dataclass(frozen=True, slots=True)
class D3Metrics:
    accuracy: float
    reward_ratio: float
    total_reward: float
    oracle_reward: float
    trade_rate: float
    dominant_action_rate: float
    invalid_action_count: int


@dataclass(frozen=True, slots=True)
class D3TrainedArm:
    model: D3Predictor
    normalizer: D3Normalizer

    def save(self, directory: Path, *, arm: str, seed: int) -> None:
        target = directory / "models" / arm / f"seed-{seed}"
        target.mkdir(parents=True, exist_ok=False)
        self.model.save(target / "model")
        self.normalizer.save(target / "normalizer.pkl")


def shuffled_d3_episodes(episodes: Sequence[D3Episode], *, seed: int) -> tuple[D3Episode, ...]:
    rewards = [tuple(candidate[2] for candidate in episode.candidates) for episode in episodes]
    random.Random(seed).shuffle(rewards)
    return tuple(
        D3Episode(
            decision_date=episode.decision_date,
            candidates=tuple((symbol, features, reward) for (symbol, features, _), reward in zip(episode.candidates, shuffled, strict=True)),
            market_context=episode.market_context,
            progress=episode.progress,
        )
        for episode, shuffled in zip(episodes, rewards, strict=True)
    )


def train_d3_model(episodes: tuple[D3Episode, ...], *, representation: D3Representation, config: D3TrainingConfig) -> D3TrainedArm:
    """Train one PPO-only D3 unit without cloning or oracle calibration."""

    _ = prepare_torch_runtime()
    import torch
    from sb3_contrib import MaskablePPO
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    vector = DummyVecEnv([lambda: HistoricalTopKEnv(episodes, representation=representation, cost_bp=0)])
    normalizer = VecNormalize(vector, norm_obs=False, norm_reward=False)
    model = MaskablePPO(
        "MlpPolicy",
        normalizer,
        seed=config.seed,
        device="cpu",
        gamma=1.0,
        learning_rate=config.learning_rate,
        n_steps=config.n_steps,
        batch_size=config.batch_size,
        n_epochs=config.n_epochs,
        policy_kwargs={"net_arch": {"pi": [256, 128], "vf": [256, 128]}},
        verbose=0,
    )
    model.learn(total_timesteps=config.timesteps, progress_bar=False)
    return D3TrainedArm(model=model, normalizer=normalizer)


def evaluate_d3_model(
    model: D3Predictor,
    episodes: tuple[D3Episode, ...],
    *,
    representation: D3Representation,
    seed: int,
    cost_bp: int,
) -> tuple[D3Metrics, tuple[dict[str, str | int | float | None], ...]]:
    env = HistoricalTopKEnv(episodes, representation=representation, cost_bp=cost_bp)
    observation, _ = env.reset(seed=seed)
    actions: list[int] = []
    events: list[dict[str, str | int | float | None]] = []
    achieved = oracle = 0.0
    correct = invalid = 0
    for episode in episodes:
        mask = env.action_masks()
        raw_action, _ = model.predict(observation, deterministic=True, action_masks=mask)
        action = int(np.asarray(raw_action).item())
        if action < 0 or action >= len(mask) or not mask[action]:
            invalid += 1
            action = 0
        available = tuple(candidate[2] - cost_bp / 10_000 for candidate in episode.candidates[: representation.candidate_count])
        expected = max(range(len(available)), key=lambda index: available[index]) + 1 if max(available) > 0 else 0
        observation, reward, terminated, truncated, info = env.step(action)
        achieved += reward
        oracle += max(0.0, *available)
        correct += int(action == expected)
        actions.append(action)
        events.append({**info, "expected_action": expected, "reward": reward})
        if terminated or truncated:
            break
    ratio = achieved / oracle if oracle > 0 else float(abs(achieved) < 1e-12)
    dominant = Counter(actions).most_common(1)[0][1] / len(actions)
    return D3Metrics(
        accuracy=correct / len(actions),
        reward_ratio=ratio,
        total_reward=achieved,
        oracle_reward=oracle,
        trade_rate=sum(action > 0 for action in actions) / len(actions),
        dominant_action_rate=dominant,
        invalid_action_count=invalid,
    ), tuple(events)
