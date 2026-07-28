"""MaskablePPO training and replay metrics for D2 historical capacity."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
import random
from typing import Any, cast

import numpy as np

from stom_rl.rl_discovery.d2_env import D2Action, HistoricalCloseEnv, HistoricalEpisode
from stom_rl.rl_discovery.torch_runtime import prepare_torch_runtime
from stom_rl.rl_discovery.training_bundle import DiscoveryNormalizer, TrainedArm


@dataclass(frozen=True, slots=True)
class D2TrainingConfig:
    seed: int
    timesteps: int
    n_steps: int = 64
    batch_size: int = 64
    n_epochs: int = 10
    learning_rate: float = 1e-3
    gamma: float = 1.0
    ent_coef: float = 0.0


@dataclass(frozen=True, slots=True)
class D2Metrics:
    accuracy: float
    reward_ratio: float
    total_reward: float
    oracle_reward: float
    buy_rate: float
    dominant_action_rate: float
    invalid_action_count: int


def shuffled_episodes(
    episodes: Sequence[HistoricalEpisode],
    *,
    seed: int,
) -> tuple[HistoricalEpisode, ...]:
    rewards = [episode.gross_return for episode in episodes]
    random.Random(seed).shuffle(rewards)
    return tuple(
        HistoricalEpisode(
            decision_date=episode.decision_date,
            symbol=episode.symbol,
            observation=episode.observation,
            gross_return=reward,
        )
        for episode, reward in zip(episodes, rewards, strict=True)
    )


def train_d2_model(
    episodes: tuple[HistoricalEpisode, ...],
    *,
    config: D2TrainingConfig,
) -> TrainedArm:
    """Train PPO only; no behavior cloning or oracle calibration is permitted."""

    _ = prepare_torch_runtime()
    import torch
    from sb3_contrib import MaskablePPO
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    vector = DummyVecEnv([lambda: HistoricalCloseEnv(episodes, cost_bp=0)])
    normalizer = VecNormalize(vector, norm_obs=False, norm_reward=False)
    model = MaskablePPO(
        "MlpPolicy",
        normalizer,
        seed=config.seed,
        device="cpu",
        gamma=config.gamma,
        learning_rate=config.learning_rate,
        n_steps=config.n_steps,
        batch_size=config.batch_size,
        ent_coef=config.ent_coef,
        n_epochs=config.n_epochs,
        policy_kwargs={"net_arch": {"pi": [128, 64], "vf": [128, 64]}},
        verbose=0,
    )
    _ = model.learn(total_timesteps=config.timesteps, progress_bar=False)
    return TrainedArm(model=model, normalizer=cast(DiscoveryNormalizer, cast(object, normalizer)))


def evaluate_d2_model(
    model: Any,
    episodes: tuple[HistoricalEpisode, ...],
    *,
    seed: int,
    cost_bp: int,
) -> tuple[D2Metrics, tuple[dict[str, Any], ...]]:
    env = HistoricalCloseEnv(episodes, cost_bp=cost_bp)
    observation, _ = env.reset(seed=seed)
    events: list[dict[str, Any]] = []
    actions: list[int] = []
    achieved = 0.0
    oracle = 0.0
    correct = 0
    invalid = 0
    for episode in episodes:
        mask = env.action_masks()
        raw_action, _ = model.predict(observation, deterministic=True, action_masks=mask)
        action = int(np.asarray(raw_action).item())
        if action < 0 or action >= len(mask) or not mask[action]:
            invalid += 1
            action = int(D2Action.STOP)
        expected = int(D2Action.BUY if episode.gross_return > cost_bp / 10_000 else D2Action.STOP)
        next_observation, reward, terminated, truncated, info = env.step(action)
        actions.append(action)
        achieved += reward
        oracle += max(episode.gross_return - cost_bp / 10_000, 0.0)
        correct += int(action == expected)
        events.append({**info, "expected_action": expected, "reward": reward})
        observation = next_observation
        if terminated or truncated:
            break
    ratio = _reward_ratio(achieved, oracle)
    dominant = Counter(actions).most_common(1)[0][1] / len(actions)
    return D2Metrics(
        accuracy=correct / len(actions),
        reward_ratio=ratio,
        total_reward=achieved,
        oracle_reward=oracle,
        buy_rate=sum(action == D2Action.BUY for action in actions) / len(actions),
        dominant_action_rate=dominant,
        invalid_action_count=invalid,
    ), tuple(events)


def _reward_ratio(achieved: float, oracle: float) -> float:
    if oracle > 0:
        return achieved / oracle
    return 1.0 if abs(achieved) < 1e-12 else min(0.0, achieved)
