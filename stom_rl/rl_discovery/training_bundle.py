"""Atomic persistence contract for one trained discovery arm."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile
from typing import Protocol

from stom_rl.rl_discovery.storage import UnsafeArtifactPathError, contained_path


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
        _write_model_bundle(
            run_dir,
            arm=arm,
            seed=seed,
            model=self.model,
            normalizer=self.normalizer,
        )


def _write_model_bundle(
    run_dir: Path,
    *,
    arm: str,
    seed: int,
    model: DiscoveryModel,
    normalizer: DiscoveryNormalizer,
) -> None:
    arm_dir = contained_path(run_dir, "models", arm)
    arm_dir.mkdir(parents=True, exist_ok=True)
    final_dir = contained_path(run_dir, "models", arm, f"seed-{seed}")
    temporary = Path(tempfile.mkdtemp(prefix=f".seed-{seed}.", dir=arm_dir))
    backup = Path(tempfile.mkdtemp(prefix=f".seed-{seed}.backup.", dir=arm_dir))
    backup.rmdir()
    try:
        model_path = temporary / "model.zip"
        normalizer_path = temporary / "normalizer.pkl"
        model.save(str(model_path))
        normalizer.save(str(normalizer_path))
        if not model_path.is_file() or not normalizer_path.is_file():
            raise UnsafeArtifactPathError(temporary, "model bundle is incomplete")
        _fsync_file(model_path)
        _fsync_file(normalizer_path)
        if final_dir.exists():
            os.replace(final_dir, backup)
        try:
            os.replace(temporary, final_dir)
        except OSError:
            if backup.exists() and not final_dir.exists():
                os.replace(backup, final_dir)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup.exists() and final_dir.exists():
            shutil.rmtree(backup)


def _fsync_file(path: Path) -> None:
    with path.open("r+b") as handle:
        os.fsync(handle.fileno())
