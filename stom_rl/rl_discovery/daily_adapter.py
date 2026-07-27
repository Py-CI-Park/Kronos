"""Typed lazy boundary around the heavyweight Type1 training module."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, cast

from stom_rl.rl_discovery.contract import DiscoveryPreregistration
from stom_rl.rl_discovery.gates import RunProfile
from stom_rl.rl_discovery.training_bundle import DiscoveryModel

if TYPE_CHECKING:
    from stom_rl.daily_type1_train import TrainingConfig


def build_training_config(
    seed: int,
    profile: RunProfile,
    prereg: DiscoveryPreregistration,
) -> TrainingConfig:
    """Create the frozen Type1 config through one lazy heavyweight import."""

    from stom_rl.daily_type1_train import TrainingConfig

    timesteps = (
        prereg.training.smoke_timesteps
        if profile is RunProfile.SMOKE
        else prereg.training.primary_timesteps
    )
    return TrainingConfig(
        seed=seed,
        synthetic_timesteps=timesteps,
        n_steps=64 if profile is RunProfile.SMOKE else 1000,
        batch_size=64 if profile is RunProfile.SMOKE else 250,
        n_epochs=2 if profile is RunProfile.SMOKE else 10,
        oracle_calibration_epochs=20 if profile is RunProfile.SMOKE else 200,
    )


def load_fixture_pairs(path: Path) -> Sequence[Mapping[str, object]]:
    """Load strict train-only pairs without importing Torch at module import time."""

    from stom_rl.daily_type1_train import load_synthetic_fixture

    return cast(Sequence[Mapping[str, object]], load_synthetic_fixture(path))


def evaluate_discovery_model(
    model: DiscoveryModel,
    pairs: Sequence[Mapping[str, object]],
    *,
    seed: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Normalize the legacy evaluator payload at one lazy adapter boundary."""

    from stom_rl.daily_type1_train import evaluate_model

    return cast(
        tuple[list[dict[str, object]], dict[str, object]],
        evaluate_model(model, pairs, seed=seed),
    )
