"""Durable atomic file publication primitives."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import TypeAlias

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)


def atomic_write_json(path: Path, payload: JsonValue) -> None:
    """Write JSON through an exclusive random sibling and fsync before replace."""

    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    atomic_write_bytes(path, encoded)


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Write exact input bytes through an exclusive durable sibling."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            _ = handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
