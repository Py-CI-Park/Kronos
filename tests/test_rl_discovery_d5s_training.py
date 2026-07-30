from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from stom_rl.rl_discovery.d5s_training import D5SLineage, advance_d5s_lineage


class _FakeModel:
    def __init__(self) -> None:
        self.calls: list[tuple[int, bool]] = []

    def learn(self, *, total_timesteps: int, reset_num_timesteps: bool, progress_bar: bool) -> _FakeModel:
        del progress_bar
        self.calls.append((total_timesteps, reset_num_timesteps))
        return self

    def predict(self, observation: NDArray[np.float32], *, deterministic: bool) -> tuple[NDArray[np.generic], tuple[NDArray[np.float32], ...] | None]:
        del observation, deterministic
        return np.asarray([0]), None

    def save(self, path: Path) -> None:
        del path


def test_d5s_lineage_advances_by_delta_without_reset() -> None:
    model = _FakeModel()
    first = advance_d5s_lineage(D5SLineage(model, 0), target_steps=50_000)
    second = advance_d5s_lineage(first, target_steps=100_000)

    assert second.trained_steps == 100_000
    assert model.calls == [(50_000, False), (50_000, False)]
