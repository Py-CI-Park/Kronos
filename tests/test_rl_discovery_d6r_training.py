from pathlib import Path
from typing import Self

import pytest

from stom_rl.rl_discovery.d6r_training import (
    D6RLineage,
    D6RTrainingError,
    advance_d6r_lineage,
    training_penalty_bp,
)


class _FakeModel:
    """Mutable call recorder required to observe the training boundary."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, bool, bool]] = []

    def learn(self, *, total_timesteps: int, reset_num_timesteps: bool, progress_bar: bool) -> Self:
        self.calls.append((total_timesteps, reset_num_timesteps, progress_bar))
        return self

    def save(self, path: Path) -> None:
        _ = path


def test_d6r_training_profiles_map_to_the_registered_trade_penalties() -> None:
    # Given / When / Then
    assert training_penalty_bp("COST_ONLY") == 0
    assert training_penalty_bp("TURNOVER_10BP") == 10


def test_d6r_lineage_advances_without_resetting_replay_state() -> None:
    # Given
    model = _FakeModel()
    lineage = D6RLineage(model, 0)

    # When
    advanced = advance_d6r_lineage(lineage, target_steps=4_096)

    # Then
    assert advanced.trained_steps == 4_096
    assert model.calls == [(4_096, False, False)]


def test_d6r_lineage_rejects_a_nonadvancing_target() -> None:
    # Given
    lineage = D6RLineage(_FakeModel(), 4_096)

    # When / Then
    with pytest.raises(D6RTrainingError):
        advance_d6r_lineage(lineage, target_steps=4_096)
