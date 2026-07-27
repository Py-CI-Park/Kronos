"""Atomic persistence contract for one trained discovery arm."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from stom_rl.rl_discovery.storage import write_model_bundle


class DiscoveryModel(Protocol):
    """Minimal model surface required by the attribution runner."""

    def learn(self, *, total_timesteps: int, progress_bar: bool) -> object: ...

    def save(self, path: str) -> None: ...


class DiscoveryNormalizer(Protocol):
    """Persisted observation/reward normalization contract."""

    def save(self, path: str) -> None: ...


@dataclass(frozen=True, slots=True)
class TrainedArm:
    """Model bundle that must remain loadable after a run is interrupted."""

    model: DiscoveryModel
    normalizer: DiscoveryNormalizer

    def save(self, run_dir: Path, *, arm: str, seed: int) -> None:
        write_model_bundle(
            run_dir,
            arm=arm,
            seed=seed,
            model=self.model,
            normalizer=self.normalizer,
        )
