"""Bounded, read-only telemetry snapshots for recorded RL event streams."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import pairwise
from pathlib import Path
from typing import Final, TypedDict

from pydantic import JsonValue, TypeAdapter, ValidationError

from stom_rl.rl_events import (
    EQUITY_KINDS,
    METRIC_UNITS,
    REWARD_KINDS,
    resolve_event_metric_metadata,
)
from webui.v6_research_metadata import observe_metadata
from webui.v6_research_catalog import discover_run_directories, research_lane
from webui.v6_telemetry_file_custody import (
    advanced_since_previous_poll,
    sampled_lines,
)

EVENT_FILE: Final = "rl_live_events.jsonl"
HALF_SCAN_BYTES: Final = 2 * 1024 * 1024
ACTIVE_WINDOW_SECONDS: Final = 30.0
JSON_OBJECT_ADAPTER: Final = TypeAdapter(dict[str, JsonValue])


class TelemetryPointPayload(TypedDict):
    step: int
    phase: str
    reward: float | None
    equity: float | None
    loss: float | None
    exploration: float | None
    action_name: str
    timestamp: str
    decision_timestamp: str | None
    reward_observed_at: str | None
    reward_kind: str | None
    reward_unit: str | None
    equity_kind: str | None
    equity_unit: str | None
    action_recorded: bool | None
    telemetry_live_stream: bool | None
    telemetry_producer_state: str | None


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
    decision_timestamp: str | None
    reward_observed_at: str | None
    reward_kind: str | None
    reward_unit: str | None
    equity_kind: str | None
    equity_unit: str | None
    action_recorded: bool | None
    telemetry_live_stream: bool | None
    telemetry_producer_state: str | None

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
            "decision_timestamp": self.decision_timestamp,
            "reward_observed_at": self.reward_observed_at,
            "reward_kind": self.reward_kind,
            "reward_unit": self.reward_unit,
            "equity_kind": self.equity_kind,
            "equity_unit": self.equity_unit,
            "action_recorded": self.action_recorded,
            "telemetry_live_stream": self.telemetry_live_stream,
            "telemetry_producer_state": self.telemetry_producer_state,
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


def _text(mapping: Mapping[str, JsonValue], key: str) -> str:
    value = mapping.get(key)
    return value.strip() if type(value) is str and value.strip() else "MISSING"


def _number(mapping: Mapping[str, JsonValue], key: str) -> float | None:
    value = mapping.get(key)
    if type(value) is int:
        numeric = float(value)
    elif type(value) is float:
        numeric = value
    else:
        return None
    return numeric if math.isfinite(numeric) else None


def _optional_text(mapping: Mapping[str, JsonValue], key: str) -> str | None:
    value = mapping.get(key)
    return value.strip() if type(value) is str and value.strip() else None


def _declared_text(
    metadata: Mapping[str, object],
    key: str,
    allowed: tuple[str, ...],
) -> str | None:
    value = metadata.get(key)
    return value if type(value) is str and value in allowed else None


def _declared_bool(metadata: Mapping[str, object], key: str) -> bool | None:
    value = metadata.get(key)
    return value if type(value) is bool else None


def _parse_line(line: str) -> TelemetryPoint | None:
    try:
        raw = JSON_OBJECT_ADAPTER.validate_json(line)
    except ValidationError:
        return None
    step = raw.get("global_step")
    if type(step) is not int or step < 0:
        return None
    metadata = resolve_event_metric_metadata(raw)
    timestamp = _text(raw, "timestamp_utc")
    if timestamp == "MISSING":
        timestamp = _text(raw, "timestamp")
    live_value = raw.get("telemetry_live_stream")
    producer_value = raw.get("telemetry_producer_state")
    return TelemetryPoint(
        step=step,
        phase=_text(raw, "phase"),
        reward=_number(raw, "reward"),
        equity=_number(raw, "equity"),
        loss=_number(raw, "loss"),
        exploration=_number(raw, "exploration"),
        action_name=_text(raw, "action_name"),
        timestamp=timestamp,
        decision_timestamp=_optional_text(raw, "decision_timestamp"),
        reward_observed_at=_optional_text(raw, "reward_observed_at"),
        reward_kind=_declared_text(metadata, "reward_kind", REWARD_KINDS),
        reward_unit=_declared_text(metadata, "reward_unit", METRIC_UNITS),
        equity_kind=_declared_text(metadata, "equity_kind", EQUITY_KINDS),
        equity_unit=_declared_text(metadata, "equity_unit", METRIC_UNITS),
        action_recorded=_declared_bool(metadata, "action_recorded"),
        telemetry_live_stream=live_value if type(live_value) is bool else None,
        telemetry_producer_state=(
            producer_value if type(producer_value) is str else None
        ),
    )


def _downsample(
    points: tuple[TelemetryPoint, ...], limit: int
) -> tuple[TelemetryPoint, ...]:
    if len(points) <= limit:
        return points
    indices = tuple(
        round(index * (len(points) - 1) / (limit - 1)) for index in range(limit)
    )
    return tuple(points[index] for index in dict.fromkeys(indices))


def read_telemetry(
    directory: Path,
    *,
    limit: int = 240,
    now: datetime | None = None,
) -> TelemetrySnapshot:
    """Read a bounded full or head/tail snapshot from one direct event file."""
    event_path = directory / EVENT_FILE
    if not event_path.is_file() or event_path.is_symlink():
        raise FileNotFoundError(event_path)
    lines, sampling, stat_result = sampled_lines(
        event_path,
        half_scan_bytes=HALF_SCAN_BYTES,
    )
    parsed = tuple(_parse_line(line) for line in lines if line.strip())
    points = tuple(point for point in parsed if point is not None)
    invalid_lines = len(parsed) - len(points)
    observed_now = now or datetime.now(tz=timezone.utc)
    modified = datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc)
    age = (observed_now - modified).total_seconds()
    step_advancing = len(points) >= 2 and all(
        right.step > left.step for left, right in pairwise(points)
    )
    explicitly_live = (
        sampling == "FULL_FILE"
        and invalid_lines == 0
        and step_advancing
        and all(
            point.telemetry_live_stream is True
            and point.telemetry_producer_state == "RUNNING"
            for point in points
        )
    )
    advanced_since_poll = advanced_since_previous_poll(
        event_path,
        stat_result,
        last_step=points[-1].step if points else None,
    )
    follow_mode = (
        "FOLLOWING_FILE"
        if explicitly_live and advanced_since_poll and 0 <= age <= ACTIVE_WINDOW_SECONDS
        else "HISTORICAL_SNAPSHOT"
    )
    return TelemetrySnapshot(
        points=_downsample(points, limit),
        event_bytes=stat_result.st_size,
        invalid_lines=invalid_lines,
        sampling=sampling,
        follow_mode=follow_mode,
        updated_at=modified.isoformat().replace("+00:00", "Z"),
    )


def discover_telemetry_runs(root: Path) -> tuple[TelemetryRun, ...]:
    rows: list[TelemetryRun] = []
    for run_id, directory in discover_run_directories(root):
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
