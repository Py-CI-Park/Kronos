from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Protocol, Self

import numpy as np
from numpy.typing import NDArray


class Environment(Protocol):
    pass


class DQN:
    def __init__(
        self,
        policy: str,
        env: Environment,
        *,
        seed: int,
        device: str,
        gamma: float,
        learning_rate: float,
        buffer_size: int,
        learning_starts: int,
        batch_size: int,
        train_freq: int,
        gradient_steps: int,
        target_update_interval: int,
        exploration_fraction: float,
        exploration_final_eps: float,
        policy_kwargs: Mapping[str, Sequence[int]],
        verbose: int,
    ) -> None: ...

    @classmethod
    def load(cls, path: str | Path, *, device: str) -> Self: ...

    def predict(
        self,
        observation: NDArray[np.float32],
        *,
        deterministic: bool,
    ) -> tuple[NDArray[np.generic], tuple[NDArray[np.float32], ...] | None]: ...

    def learn(
        self,
        *,
        total_timesteps: int,
        reset_num_timesteps: bool,
        progress_bar: bool,
    ) -> Self: ...

    def save(self, path: Path) -> None: ...
