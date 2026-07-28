"""Compact-policy training and economic evaluation for Type2-D1."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import random
from typing import Any

import numpy as np

from stom_rl.rl_discovery.d1_contract import D1ArmId, D1RewardKind
from stom_rl.rl_discovery.d1_env import BinaryAction, BinaryCandidateEnv
from stom_rl.rl_discovery.d1_gates import D1Outcome
from stom_rl.rl_discovery.torch_runtime import prepare_torch_runtime
from stom_rl.rl_discovery.training_bundle import TrainedArm


class D1TrainingInvariantError(RuntimeError):
    """Raised when the frozen D1 evaluation fixture violates its contract."""


@dataclass(frozen=True, slots=True)
class D1TrainingConfig:
    """Fixed compact MaskablePPO hyperparameters."""

    seed: int
    timesteps: int
    n_steps: int = 128
    batch_size: int = 64
    n_epochs: int = 4
    learning_rate: float = 3e-4
    gamma: float = 1.0
    ent_coef: float = 0.01


def train_d1_arm(
    pairs: Sequence[Mapping[str, Any]],
    *,
    arm: D1ArmId,
    reward_kind: D1RewardKind,
    config: D1TrainingConfig,
) -> TrainedArm:
    """Train one compact two-action PPO arm on train-only pairs."""

    _ = prepare_torch_runtime()
    import torch
    from sb3_contrib import MaskablePPO
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    training_pairs = _training_pairs(pairs, arm=arm, seed=config.seed)
    env_reward = (
        D1RewardKind.FIRST_DECISION_DIAGNOSTIC
        if reward_kind is D1RewardKind.FIRST_DECISION_DIAGNOSTIC
        else D1RewardKind.NATIVE_ECONOMIC
    )
    vec_env = DummyVecEnv([lambda: BinaryCandidateEnv(training_pairs, reward_kind=env_reward)])
    normalizer = VecNormalize(vec_env, norm_obs=False, norm_reward=True)
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
        policy_kwargs={"net_arch": {"pi": [64, 32], "vf": [64, 32]}},
        verbose=0,
    )
    _ = model.learn(total_timesteps=config.timesteps, progress_bar=False)
    return TrainedArm(model=model, normalizer=normalizer)


def evaluate_d1_arm(
    model: Any,
    pairs: Sequence[Mapping[str, Any]],
    *,
    arm: D1ArmId,
    seed: int,
    training_timesteps: int,
) -> tuple[D1Outcome, tuple[dict[str, Any], ...]]:
    """Evaluate a D1 model on original native economic reward only."""

    env = BinaryCandidateEnv(pairs, reward_kind=D1RewardKind.NATIVE_ECONOMIC)
    observation, _ = env.reset(seed=seed)
    events: list[dict[str, Any]] = []
    initial_actions: list[int] = []
    initial_correct = 0
    invalid_count = 0
    block_count = 0
    no_fill_count = 0
    achieved_reward = 0.0
    while True:
        call_index = len(events) % 10
        expected = int(BinaryAction.SELECT_TOP_OBSERVED if call_index == 0 and observation[1] > 0 else BinaryAction.STOP)
        mask = env.action_masks()
        raw_action, _ = model.predict(observation, deterministic=True, action_masks=mask)
        action = int(np.asarray(raw_action).item())
        if not mask[action]:
            invalid_count += 1
        next_observation, _, terminated, truncated, info = env.step(action)
        if call_index == 0:
            initial_actions.append(action)
            initial_correct += int(action == expected)
        block_count += int(info.get("status") == "BLOCK")
        settlement = info.get("settlement")
        no_fill_count += 0 if settlement is None else int(settlement.no_fill_slots)
        native_reward = float(info.get("native_economic_reward", 0.0))
        achieved_reward += native_reward
        events.append(
            {
                "pair_index": len(events) // 10,
                "call_index": call_index,
                "binary_action": action,
                "decoded_action": int(info["decoded_action"]),
                "expected_binary_action": expected,
                "native_economic_reward": native_reward,
            }
        )
        observation = next_observation
        if terminated or truncated:
            break
    oracle_reward = _oracle_reward(pairs, seed=seed)
    dominant = Counter(initial_actions).most_common(1)[0][1] / len(initial_actions)
    outcome = D1Outcome(
        arm=arm,
        seed=seed,
        training_timesteps=training_timesteps,
        economic_reward_ratio=achieved_reward / oracle_reward,
        initial_decision_accuracy=initial_correct / len(initial_actions),
        invalid_action_count=invalid_count,
        block_count=block_count,
        no_fill_count=no_fill_count,
        dominant_initial_action_rate=dominant,
    )
    return outcome, tuple(events)


def _oracle_reward(pairs: Sequence[Mapping[str, Any]], *, seed: int) -> float:
    env = BinaryCandidateEnv(pairs, reward_kind=D1RewardKind.NATIVE_ECONOMIC)
    observation, _ = env.reset(seed=seed)
    total = 0.0
    call_index = 0
    while True:
        action = BinaryAction.SELECT_TOP_OBSERVED if call_index == 0 and observation[1] > 0 else BinaryAction.STOP
        observation, _, terminated, truncated, info = env.step(action)
        total += float(info.get("native_economic_reward", 0.0))
        call_index = (call_index + 1) % 10
        if terminated or truncated:
            if total <= 0:
                raise D1TrainingInvariantError("D1 oracle economic reward must be positive")
            return total


def _training_pairs(
    pairs: Sequence[Mapping[str, Any]],
    *,
    arm: D1ArmId,
    seed: int,
) -> Sequence[Mapping[str, Any]]:
    if arm is not D1ArmId.BINARY_SHUFFLED:
        return pairs
    from stom_rl.rl_discovery.runner import shuffle_reward_pairs

    return shuffle_reward_pairs(pairs, seed=seed)
