"""Bounded, read-only telemetry snapshots for recorded RL event streams."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, TypedDict

from webui.v6_research_metadata import observe_metadata
from webui.v6_research_catalog import research_lane

EVENT_FILE: Final = "rl_live_events.jsonl"
HALF_SCAN_BYTES: Final = 2 * 1024 * 1024
ACTIVE_WINDOW_SECONDS: Final = 30.0


class TelemetryPointPayload(TypedDict):
    step: int
    phase: str
    reward: float | None
    equity: float | None
    loss: float | None
    exploration: float | None
    action_name: str
    timestamp: str


@dataclass(frozen=True, slots=True)
class TelemetryPoint:
    step: int
    phase: str
    reward: float | None
    equity: float | None
    loss: float | None
    exploration: float | None
    action_name: str
    timestamp: str

    def to_payload(self) -> TelemetryPointPayload:
        return {
            "step": self.step,
            "phase": self.phase,
            "reward": self.reward,
            "equity": self.equity,
            "loss": self.loss,
            "exploration": self.exploration,
            "action_name": self.action_name,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True, slots=True)
class TelemetrySnapshot:
    points: tuple[TelemetryPoint, ...]
    event_bytes: int
    invalid_lines: int
    sampling: str
    follow_mode: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class TelemetryRun:
    run_id: str
    name: str
    lane: str
    status: str
    algorithm: str
    event_bytes: int
    updated_at: str
    updated_ns: int


def _text(mapping, key: str) -> str:
    value = mapping.get(key)
    return value.strip() if type(value) is str and value.strip() else "MISSING"


def _number(mapping, key: str) -> float | None:
    value = mapping.get(key)
    if type(value) not in (int, float):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _parse_line(line: str) -> TelemetryPoint | None:
    try:
        raw = json.loads(line)
    except json.JSONDecodeError:
        return None
    if type(raw) is not dict:
        return None
    step = raw.get("global_step")
    if type(step) is not int or step < 0:
        return None
    timestamp = _text(raw, "timestamp_utc")
    if timestamp == "MISSING":
        timestamp = _text(raw, "timestamp")
    return TelemetryPoint(
        step=step,
        phase=_text(raw, "phase"),
        reward=_number(raw, "reward"),
        equity=_number(raw, "equity"),
        loss=_number(raw, "loss"),
        exploration=_number(raw, "exploration"),
        action_name=_text(raw, "action_name"),
        timestamp=timestamp,
    )


def _sampled_lines(path: Path, size: int) -> tuple[tuple[str, ...], str]:
    if size <= HALF_SCAN_BYTES * 2:
        return tuple(path.read_text(encoding="utf-8-sig").splitlines()), "FULL_FILE"
    with path.open("rb") as stream:
        head = stream.read(HALF_SCAN_BYTES)
        stream.seek(-HALF_SCAN_BYTES, 2)
        tail = stream.read(HALF_SCAN_BYTES)
    head = head[: head.rfind(b"\n") + 1]
    first_break = tail.find(b"\n")
    tail = tail[first_break + 1 :] if first_break >= 0 else b""
    head_lines = head.decode("utf-8-sig").splitlines()
    tail_lines = tail.decode("utf-8").splitlines()
    return tuple(head_lines + tail_lines), "HEAD_TAIL_SAMPLE"


def _downsample(points: tuple[TelemetryPoint, ...], limit: int) -> tuple[TelemetryPoint, ...]:
    if len(points) <= limit:
        return points
    indices = tuple(round(index * (len(points) - 1) / (limit - 1)) for index in range(limit))
    return tuple(points[index] for index in dict.fromkeys(indices))


def read_telemetry(
    directory: Path,
    *,
    limit: int = 240,
    now: datetime | None = None,
) -> TelemetrySnapshot:
    """Read a bounded full or head/tail snapshot from one direct event file."""
    event_path = directory / EVENT_FILE
    stat_result = event_path.stat()
    lines, sampling = _sampled_lines(event_path, stat_result.st_size)
    parsed = tuple(_parse_line(line) for line in lines if line.strip())
    points = tuple(point for point in parsed if point is not None)
    observed_now = now or datetime.now(tz=timezone.utc)
    modified = datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc)
    age = (observed_now - modified).total_seconds()
    follow_mode = "FOLLOWING_FILE" if 0 <= age <= ACTIVE_WINDOW_SECONDS else "HISTORICAL_SNAPSHOT"
    return TelemetrySnapshot(
        points=_downsample(points, limit),
        event_bytes=stat_result.st_size,
        invalid_lines=len(parsed) - len(points),
        sampling=sampling,
        follow_mode=follow_mode,
        updated_at=modified.isoformat().replace("+00:00", "Z"),
    )


def _directories(root: Path) -> tuple[tuple[str, Path], ...]:
    try:
        top_level = tuple(path for path in root.iterdir() if path.is_dir() and not path.is_symlink())
    except OSError:
        return ()
    rows: list[tuple[str, Path]] = []
    for directory in top_level:
        if directory.name != "v6_daily_h1":
            rows.append((directory.name, directory))
            continue
        try:
            children = tuple(path for path in directory.iterdir() if path.is_dir() and not path.is_symlink())
        except OSError:
            continue
        rows.extend((f"{directory.name}/{child.name}", child) for child in children)
    return tuple(rows)


def discover_telemetry_runs(root: Path) -> tuple[TelemetryRun, ...]:
    rows: list[TelemetryRun] = []
    for run_id, directory in _directories(root):
        event_path = directory / EVENT_FILE
        if not event_path.is_file() or event_path.is_symlink():
            continue
        try:
            stat_result = event_path.stat()
        except OSError:
            continue
        modified = datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc)
        metadata = observe_metadata(directory)
        rows.append(
            TelemetryRun(
                run_id=run_id,
                name=directory.name,
                lane=research_lane(run_id),
                status=metadata.status,
                algorithm=metadata.algorithm,
                event_bytes=stat_result.st_size,
                updated_at=modified.isoformat().replace("+00:00", "Z"),
                updated_ns=stat_result.st_mtime_ns,
            )
        )
    return tuple(sorted(rows, key=lambda row: (-row.updated_ns, row.run_id)))
