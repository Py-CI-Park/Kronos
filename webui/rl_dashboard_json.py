"""Typed adapters for legacy RL dashboard JSON readers."""

# This module is the public typed boundary for one private file helper.
# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path
from typing import cast

from stom_rl.rl_discovery.storage import JsonValue

DISCOVERY_ARTIFACT_TYPES = frozenset(
    {
        "rl_discovery_d2",
        "rl_discovery_d3",
        "rl_discovery_d4",
        "rl_discovery_d5",
        "rl_discovery_d5r",
        "rl_discovery_d5s",
        "rl_discovery_d6",
    }
)

if __package__:
    from .rl_dashboard_files import _read_run_json as _legacy_read_run_json
else:  # pragma: no cover - supports direct script-style imports
    from webui.rl_dashboard_files import _read_run_json as _legacy_read_run_json


def read_run_json(run_dir: Path, path: Path) -> dict[str, JsonValue]:
    value = cast(object, _legacy_read_run_json(run_dir, path))
    return cast(dict[str, JsonValue], value) if isinstance(value, dict) else {}


def json_object(value: object) -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], value) if isinstance(value, dict) else {}


def json_objects(value: object) -> list[dict[str, JsonValue]]:
    if not isinstance(value, list):
        return []
    rows = cast(list[JsonValue], value)
    return [cast(dict[str, JsonValue], row) for row in rows if isinstance(row, dict)]
