"""Common D4 supervised labels and algorithm training adapters."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
import random
from typing import TYPE_CHECKING, Callable, Protocol, cast

import numpy as np
from numpy.typing import NDArray

from stom_rl.rl_discovery.d3_env import D3Episode, D3Representation, HistoricalTopKEnv
from stom_rl.rl_discovery.d4_contract import D4AlgorithmArmId
from stom_rl.rl_discovery.torch_runtime import prepare_torch_runtime

if TYPE_CHECKING:
    from sb3_contrib import MaskablePPO
    from stable_baselines3.common.vec_env import DummyVecEnv
    from torch import Tensor, device as TorchDevice


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
    ) -> tuple[NDArray[np.generic], object | None]: ...


class D4PlainExternalPolicy(D4ExternalPolicy, Protocol):
    def predict(
        self,
        observation: NDArray[np.float32],
        *,
        deterministic: bool,
    ) -> tuple[NDArray[np.generic], object | None]: ...


class _MaskableTrainable(D4MaskedExternalPolicy, Protocol):
    def learn(self, *, total_timesteps: int, progress_bar: bool) -> object: ...


class _PlainTrainable(D4PlainExternalPolicy, Protocol):
    def learn(self, *, total_timesteps: int, progress_bar: bool) -> object: ...


class _CategoricalSurface(Protocol):
    logits: Tensor


class _DistributionSurface(Protocol):
    distribution: _CategoricalSurface


class _AuxiliaryPolicySurface(Protocol):
    def parameters(self) -> Iterator[Tensor]: ...
    def get_distribution(self, observation: Tensor, *, action_masks: object | None) -> _DistributionSurface: ...


class _AuxiliaryModelSurface(Protocol):
    device: TorchDevice
    policy: _AuxiliaryPolicySurface


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
        actions, _state = self.model.predict(observation, deterministic=deterministic, action_masks=action_masks)
        return np.asarray(actions, dtype=np.int64), None

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
        actions, _state = self.model.predict(observation, deterministic=deterministic)
        return np.asarray(actions, dtype=np.int64), None

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
    manual_seed = cast(Callable[[int], object], torch.manual_seed)
    _ = manual_seed(config.seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    vector = DummyVecEnv([
        lambda: _new_environment(episodes, representation),
    ])
    match config.arm:
        case D4AlgorithmArmId.SUPERVISED_CEILING:
            supervised = cast(_MaskableTrainable, cast(object, _new_maskable_ppo(vector, config.seed)))
            _pretrain_policy(supervised, episodes, representation, config.supervised_epochs)
            return D4TrainedArm(D4MaskedPolicy(supervised))
        case D4AlgorithmArmId.PPO_BASELINE:
            ppo = cast(_MaskableTrainable, cast(object, _new_maskable_ppo(vector, config.seed)))
            _ = ppo.learn(total_timesteps=config.rl_timesteps, progress_bar=False)
            return D4TrainedArm(D4MaskedPolicy(ppo))
        case D4AlgorithmArmId.DQN_DISCRETE:
            dqn = cast(_PlainTrainable, cast(object, DQN(
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
            )))
            _ = dqn.learn(total_timesteps=config.rl_timesteps, progress_bar=False)
            return D4TrainedArm(D4PlainPolicy(dqn))
        case D4AlgorithmArmId.AUXILIARY_PPO:
            auxiliary = cast(_MaskableTrainable, cast(object, _new_maskable_ppo(vector, config.seed)))
            _pretrain_policy(auxiliary, episodes, representation, config.supervised_epochs)
            _ = auxiliary.learn(total_timesteps=config.rl_timesteps, progress_bar=False)
            return D4TrainedArm(D4MaskedPolicy(auxiliary))


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
    model: _MaskableTrainable,
    episodes: tuple[D3Episode, ...],
    representation: D3Representation,
    epochs: int,
) -> None:
    import torch
    from torch.nn import functional

    observations, actions = supervised_examples(episodes, representation=representation)
    surface = cast(_AuxiliaryModelSurface, cast(object, model))
    tensor = torch.as_tensor(observations, dtype=torch.float32, device=surface.device)
    labels = torch.as_tensor(actions, dtype=torch.long, device=surface.device)
    masks = torch.ones((len(episodes), representation.action_count), dtype=torch.bool, device=surface.device)
    optimizer = torch.optim.Adam(surface.policy.parameters(), lr=1e-3)
    for _ in range(epochs):
        distribution = surface.policy.get_distribution(tensor, action_masks=masks)
        loss = functional.cross_entropy(distribution.distribution.logits, labels)
        optimizer.zero_grad()
        backward = cast(Callable[[], object], loss.backward)
        step = cast(Callable[[], object], optimizer.step)
        _ = backward()
        _ = step()
