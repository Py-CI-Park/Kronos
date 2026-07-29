"""Common D4 supervised labels and algorithm training adapters."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import random
from typing import TYPE_CHECKING, Protocol, assert_never

import numpy as np
from numpy.typing import NDArray

from stom_rl.rl_discovery.d3_env import D3Episode, D3Representation, HistoricalTopKEnv
from stom_rl.rl_discovery.d4_contract import D4AlgorithmArmId
from stom_rl.rl_discovery.torch_runtime import prepare_torch_runtime

if TYPE_CHECKING:
    from sb3_contrib import MaskablePPO
    from stable_baselines3.common.vec_env import DummyVecEnv


class D4ExternalPolicy(Protocol):
    """Minimal saved policy surface wrapped by D4 evaluation."""

    def save(self, path: Path) -> None: ...


class D4MaskedExternalPolicy(D4ExternalPolicy, Protocol):
    def predict(
        self,
        observation: NDArray[np.float32],
        *,
        deterministic: bool,
        action_masks: NDArray[np.bool_],
    ) -> tuple[NDArray[np.int64], None]: ...


class D4PlainExternalPolicy(D4ExternalPolicy, Protocol):
    def predict(
        self,
        observation: NDArray[np.float32],
        *,
        deterministic: bool,
    ) -> tuple[NDArray[np.int64], None]: ...


@dataclass(frozen=True, slots=True)
class D4MaskedPolicy:
    model: D4MaskedExternalPolicy

    def predict(
        self,
        observation: NDArray[np.float32],
        *,
        deterministic: bool,
        action_masks: NDArray[np.bool_],
    ) -> tuple[NDArray[np.int64], None]:
        return self.model.predict(observation, deterministic=deterministic, action_masks=action_masks)

    def save(self, path: Path) -> None:
        self.model.save(path)


@dataclass(frozen=True, slots=True)
class D4PlainPolicy:
    model: D4PlainExternalPolicy

    def predict(
        self,
        observation: NDArray[np.float32],
        *,
        deterministic: bool,
        action_masks: NDArray[np.bool_],
    ) -> tuple[NDArray[np.int64], None]:
        _ = action_masks
        return self.model.predict(observation, deterministic=deterministic)

    def save(self, path: Path) -> None:
        self.model.save(path)


@dataclass(frozen=True, slots=True)
class D4TrainingConfig:
    arm: D4AlgorithmArmId
    seed: int
    rl_timesteps: int
    supervised_epochs: int


@dataclass(frozen=True, slots=True)
class D4TrainedArm:
    policy: D4MaskedPolicy | D4PlainPolicy

    def save(self, directory: Path, *, arm: str, seed: int) -> None:
        target = directory / "models" / arm / f"seed-{seed}"
        target.mkdir(parents=True, exist_ok=False)
        self.policy.save(target / "model")


def supervised_examples(
    episodes: Sequence[D3Episode],
    *,
    representation: D3Representation,
) -> tuple[NDArray[np.float32], NDArray[np.int64]]:
    """Create observable tensors and post-action labels for train-only diagnostics."""

    observations = np.asarray(
        [representation.observation(episode) for episode in episodes],
        dtype=np.float32,
    )
    actions = np.asarray(
        [_oracle_action(episode, candidate_count=representation.candidate_count) for episode in episodes],
        dtype=np.int64,
    )
    return observations, actions


def _oracle_action(episode: D3Episode, *, candidate_count: int) -> int:
    rewards = tuple(candidate[2] for candidate in episode.candidates[:candidate_count])
    best = max(range(len(rewards)), key=rewards.__getitem__)
    return best + 1 if rewards[best] > 0 else 0


def train_d4_model(
    episodes: tuple[D3Episode, ...],
    *,
    representation: D3Representation,
    config: D4TrainingConfig,
) -> D4TrainedArm:
    """Train one preregistered D4 diagnostic or RL policy."""

    _ = prepare_torch_runtime()
    import torch
    from stable_baselines3 import DQN
    from stable_baselines3.common.vec_env import DummyVecEnv

    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    vector = DummyVecEnv([
        lambda: _new_environment(episodes, representation),
    ])
    match config.arm:
        case D4AlgorithmArmId.SUPERVISED_CEILING:
            model = _new_maskable_ppo(vector, config.seed)
            _pretrain_policy(model, episodes, representation, config.supervised_epochs)
            return D4TrainedArm(D4MaskedPolicy(model))
        case D4AlgorithmArmId.PPO_BASELINE:
            model = _new_maskable_ppo(vector, config.seed)
            model.learn(total_timesteps=config.rl_timesteps, progress_bar=False)
            return D4TrainedArm(D4MaskedPolicy(model))
        case D4AlgorithmArmId.DQN_DISCRETE:
            model = DQN(
                "MlpPolicy",
                vector,
                seed=config.seed,
                device="cpu",
                gamma=1.0,
                learning_rate=1e-3,
                buffer_size=max(2048, config.rl_timesteps),
                learning_starts=min(128, config.rl_timesteps // 4),
                batch_size=64,
                train_freq=4,
                gradient_steps=1,
                policy_kwargs={"net_arch": [256, 128]},
                verbose=0,
            )
            model.learn(total_timesteps=config.rl_timesteps, progress_bar=False)
            return D4TrainedArm(D4PlainPolicy(model))
        case D4AlgorithmArmId.AUXILIARY_PPO:
            model = _new_maskable_ppo(vector, config.seed)
            _pretrain_policy(model, episodes, representation, config.supervised_epochs)
            model.learn(total_timesteps=config.rl_timesteps, progress_bar=False)
            return D4TrainedArm(D4MaskedPolicy(model))
        case unreachable:
            assert_never(unreachable)


def _new_environment(episodes: tuple[D3Episode, ...], representation: D3Representation) -> HistoricalTopKEnv:
    return HistoricalTopKEnv(episodes, representation=representation, cost_bp=0)


def _new_maskable_ppo(vector: DummyVecEnv, seed: int) -> MaskablePPO:
    from sb3_contrib import MaskablePPO

    return MaskablePPO(
        "MlpPolicy",
        vector,
        seed=seed,
        device="cpu",
        gamma=1.0,
        learning_rate=1e-3,
        n_steps=128,
        batch_size=64,
        n_epochs=10,
        policy_kwargs={"net_arch": {"pi": [256, 128], "vf": [256, 128]}},
        verbose=0,
    )


def _pretrain_policy(
    model: MaskablePPO,
    episodes: tuple[D3Episode, ...],
    representation: D3Representation,
    epochs: int,
) -> None:
    import torch
    from torch.nn import functional

    observations, actions = supervised_examples(episodes, representation=representation)
    tensor = torch.as_tensor(observations, dtype=torch.float32, device=model.device)
    labels = torch.as_tensor(actions, dtype=torch.long, device=model.device)
    masks = torch.ones((len(episodes), representation.action_count), dtype=torch.bool, device=model.device)
    optimizer = torch.optim.Adam(model.policy.parameters(), lr=1e-3)
    for _ in range(epochs):
        distribution = model.policy.get_distribution(tensor, action_masks=masks)
        loss = functional.cross_entropy(distribution.distribution.logits, labels)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
