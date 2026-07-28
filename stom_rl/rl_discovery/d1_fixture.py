"""Lazy train-only fixture boundary for D1."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from stom_rl.rl_discovery.torch_runtime import prepare_torch_runtime


def load_d1_fixture(path: Path) -> Sequence[Mapping[str, Any]]:
    """Load the strict synthetic fixture after preparing the native runtime."""

    _ = prepare_torch_runtime()
    from stom_rl.daily_type1_train import load_synthetic_fixture

    return cast(Sequence[Mapping[str, Any]], load_synthetic_fixture(path))
