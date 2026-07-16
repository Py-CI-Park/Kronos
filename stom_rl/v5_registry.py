"""SQLite-backed canonical registry for Kronos RL V5 run snapshots.

The registry journal stores complete RFC 8785/JCS run-state snapshots.  Every
journal row is hash-chained by exact record bytes so backend readers can serve a
stable, fail-closed view without reconstructing mutable patches.
"""
from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import math
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3
import threading
from typing import Any, Final
import uuid

import rfc8785


REGISTRY_SCHEMA: Final = "kronos_rl_registry.v2"
RUN_STATE_SCHEMA: Final = "kronos_rl_run_state.v2"
REGISTRY_RECORD_SCHEMA: Final = "kronos_rl_registry_record.v2"
CURSOR_SCHEMA: Final = "kronos-run-cursor.v1"
RECORD_DOMAIN: Final = b"KRONOS-RL-REGISTRY-RECORD-V2\x00"
ZERO_SHA256: Final = "0" * 64
DEFAULT_CURSOR_KEY_ID: Final = "kronos-v5-registry-cursor-key-1"
CURSOR_TTL: Final = timedelta(seconds=900)
MAX_LIST_LIMIT: Final = 100
MAX_EVENTS_LIMIT: Final = 500
MAX_ARTIFACTS: Final = 1000
SAFE_INTEGER_MAX: Final = 9007199254740991

SIX_FALSE_LOCKS: Final = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}

RUN_SNAPSHOT_REQUIRED_KEYS: Final = frozenset(
    {
        "schema_version",
        "run_uid",
        "run_revision",
        "display",
        "protocol",
        "source",
        "data",
        "phase",
        "terminal",
        "liveness",
        "attempts",
        "cells",
        "progress",
        "heartbeat",
        "blockers",
        "matrix",
        "artifacts",
        "locks",
        "created_utc",
        "updated_utc",
    }
)
TERMINAL_STATES: Final = frozenset({"STOPPED", "FAILED", "COMPLETED"})
LIVENESS_STATES: Final = frozenset({"UNKNOWN", "ADVANCING", "STALLED", "TERMINAL"})
PHASE_LIVENESS_MATRIX: Final = {
    "QUEUED": frozenset({"UNKNOWN"}),
    "CELL_RUNNING": frozenset({"ADVANCING", "STALLED"}),
    "RUN_TERMINAL": frozenset({"TERMINAL"}),
}
_DISPLAY_KEYS: Final = frozenset({"name", "display_sha256"})
_PROTOCOL_KEYS: Final = frozenset({"protocol_id", "protocol_sha256"})
_SOURCE_REQUIRED_KEYS: Final = frozenset({"source_sha256"})
_SOURCE_KEYS: Final = frozenset({"source_sha256", "git_commit_sha256"})
_DATA_REQUIRED_KEYS: Final = frozenset({"data_sha256"})
_DATA_KEYS: Final = frozenset({"data_sha256", "split"})
_PROGRESS_KEYS: Final = frozenset({"step", "total_steps"})
_HEARTBEAT_KEYS: Final = frozenset({"last_heartbeat_utc"})
_ATTEMPT_REQUIRED_KEYS: Final = frozenset({"attempt_uid", "status", "started_utc"})
_ATTEMPT_KEYS: Final = frozenset({"attempt_uid", "status", "started_utc", "finished_utc"})
_CELL_KEYS: Final = frozenset({"cell_uid", "attempt_uid", "status", "step"})
_ARTIFACT_REQUIRED_KEYS: Final = frozenset({"artifact_id", "created_utc", "sha256", "byte_length", "filename"})
_ARTIFACT_KEYS: Final = frozenset({"artifact_id", "created_utc", "sha256", "byte_length", "filename", "media_type", "uri", "path"})
_BLOCKER_REQUIRED_KEYS: Final = frozenset({"blocker_id", "status", "created_utc", "message"})
_BLOCKER_KEYS: Final = frozenset({"blocker_id", "status", "created_utc", "message", "resolved_utc", "severity"})
_MATRIX_KEYS: Final = frozenset({"dimensions", "cells", "missing_cell_ids", "summary", "terminal"})
_MATRIX_DIMENSION_KEYS: Final = frozenset({"seeds", "folds", "variants"})
_MATRIX_CELL_KEYS: Final = frozenset({"cell_uid", "seed", "fold", "variant", "state"})
_MATRIX_SUMMARY_KEYS: Final = frozenset({"total_cells", "completed", "failed", "pending"})
_RECORD_KEYS: Final = frozenset(
    {
        "schema_version",
        "registry_epoch",
        "global_seq",
        "run_uid",
        "run_revision",
        "attempt_uid",
        "cell_uid",
        "event_type",
        "payload_sha256",
        "previous_global_hash",
        "created_utc",
    }
)
_CURSOR_KEYS: Final = frozenset(
    {
        "schema",
        "registry_epoch",
        "snapshot_global_seq",
        "last_global_seq",
        "last_run_uid",
        "query_sha256",
        "issued_at",
        "expires_at",
        "key_id",
    }
)
_SHA_RE: Final = re.compile(r"^[0-9a-f]{64}\Z")
_UUID4_RE: Final = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
_UTC_RE: Final = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z")
_B64URL_RE: Final = re.compile(r"^[A-Za-z0-9_-]+\Z")


class RegistryError(ValueError):
    """Base class for registry failures with HTTP-compatible status metadata."""

    status_code = 500
    code = "REGISTRY_ERROR"


class BadRequest(RegistryError):
    status_code = 400
    code = "BAD_REQUEST"


class Conflict(RegistryError):
    status_code = 409
    code = "CONFLICT"


class Gone(RegistryError):
    status_code = 410
    code = "GONE"


class NotFound(RegistryError):
    status_code = 404
    code = "NOT_FOUND"


class TooLarge(RegistryError):
    status_code = 413
    code = "TOO_LARGE"


class Unavailable(RegistryError):
    status_code = 503
    code = "REGISTRY_UNAVAILABLE"


class Corrupt(Unavailable):
    code = "REGISTRY_CORRUPT"


RegistryBadRequest = BadRequest
RegistryConflict = Conflict
RegistryGone = Gone
RegistryNotFound = NotFound
RegistryTooLarge = TooLarge
RegistryUnavailable = Unavailable
RegistryCorrupt = Corrupt


@dataclass(frozen=True)
class RegistryIdentity:
    schema: str
    registry_epoch: str
    genesis_global_hash: str
    cursor_key_id: str
    created_utc: str
    read_only: bool
    corrupt_reason: str | None
    latest_global_seq: int
    latest_record_hash: str


@dataclass(frozen=True)
class SnapshotRead:
    run_uid: str
    run_revision: int
    global_seq: int
    payload_sha256: str
    record_hash: str
    created_utc: str
    snapshot: dict[str, Any]
    snapshot_global_seq: int | None = None


@dataclass(frozen=True)
class Page:
    items: tuple[SnapshotRead, ...]
    next_cursor: str | None
    snapshot_global_seq: int
    registry_epoch: str
    issued_at: str
    expires_at: str


@dataclass(frozen=True)
class EventsPage:
    items: tuple[dict[str, Any], ...]
    next_after_global_seq: int | None
    snapshot_global_seq: int
    run_uid: str
    run_revision: int


@dataclass(frozen=True)
class MatrixRead:
    run_uid: str
    run_revision: int
    global_seq: int
    snapshot_global_seq: int
    matrix: dict[str, Any]


NowSource = Callable[[], datetime | str]


def canonical_bytes(value: Any) -> bytes:
    """Return pinned RFC 8785/JCS bytes without adding a newline."""

    try:
        return rfc8785.dumps(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise BadRequest("value is not canonicalizable in the Kronos JCS profile") from exc


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def registry_record_bytes(record: Mapping[str, Any]) -> bytes:
    """Return exact bytes covered by a registry journal record hash."""

    if not isinstance(record, Mapping) or set(record) != _RECORD_KEYS:
        raise BadRequest("registry record object has the wrong field set")
    return RECORD_DOMAIN + canonical_bytes(record)


def registry_record_hash(record: Mapping[str, Any]) -> str:
    return sha256_hex(registry_record_bytes(record))


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_b64url(value: str, label: str) -> bytes:
    if not isinstance(value, str) or not value or "=" in value or not _B64URL_RE.fullmatch(value):
        raise BadRequest(f"{label} is not base64url-no-pad")
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception as exc:
        raise BadRequest(f"{label} is not base64url-no-pad") from exc
    if _b64url(raw) != value:
        raise BadRequest(f"{label} is not canonical base64url-no-pad")
    return raw


def _parse_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not _UTC_RE.fullmatch(value):
        raise BadRequest(f"{label} must be canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise BadRequest(f"{label} must be real UTC") from exc
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    value = value.astimezone(timezone.utc)
    if value.microsecond:
        return value.isoformat(timespec="microseconds").replace("+00:00", "Z")
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")

def _ensure_record_created_after(previous_created_utc: str | None, created_utc: str, label: str = "created_utc") -> None:
    current = _parse_utc(created_utc, label)
    if previous_created_utc is None:
        return
    previous = _parse_utc(previous_created_utc, "previous_created_utc")
    if current <= previous:
        raise BadRequest(f"{label} must be strictly greater than the previous registry record created_utc")



def _clone_canonical(value: Any) -> Any:
    return json.loads(canonical_bytes(value))


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise BadRequest(f"{label} must be a non-empty string")
    return value


def _require_int(value: Any, label: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= SAFE_INTEGER_MAX:
        raise BadRequest(f"{label} must be a safe integer")
    return value


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise BadRequest(f"{label} must be a lowercase SHA-256 digest")
    return value


def _contains_sha(value: Mapping[str, Any]) -> bool:
    for key, item in value.items():
        if isinstance(key, str) and (key == "sha256" or key.endswith("_sha256")) and isinstance(item, str) and _SHA_RE.fullmatch(item):
            return True
        if isinstance(item, Mapping) and _contains_sha(item):
            return True
    return False


def _json_path(value: Mapping[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _ensure_keys(value: Any, label: str, required: frozenset[str], allowed: frozenset[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BadRequest(f"{label} must be an object")
    allowed_keys = required if allowed is None else allowed
    keys = set(value)
    missing = sorted(required - keys)
    extra = sorted(keys - allowed_keys)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing {missing}")
        if extra:
            details.append(f"extra {extra}")
        raise BadRequest(f"{label} has wrong field set: {', '.join(details)}")
    return value


def _validate_number_bounds(value: Any, path: str = "snapshot") -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int):
        if not -SAFE_INTEGER_MAX <= value <= SAFE_INTEGER_MAX:
            raise BadRequest(f"{path} is outside the JCS safe integer domain")
        return
    if isinstance(value, float):
        if not math.isfinite(value) or not -SAFE_INTEGER_MAX <= value <= SAFE_INTEGER_MAX:
            raise BadRequest(f"{path} must be finite and within the JCS safe numeric domain")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_number_bounds(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_number_bounds(item, f"{path}.{key}")
        return
    raise BadRequest(f"{path} contains a non-JSON value")


def _require_optional_text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, label)


def _require_text_array(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise BadRequest(f"{label} must be an array")
    items = tuple(_require_text(item, f"{label}[]") for item in value)
    if len(items) != len(set(items)):
        raise BadRequest(f"{label} must not contain duplicates")
    return items


def _progress_pair(snapshot: Mapping[str, Any]) -> tuple[int, int]:
    progress = _ensure_keys(snapshot.get("progress"), "progress", _PROGRESS_KEYS)
    step = _require_int(progress["step"], "progress.step")
    total = _require_int(progress["total_steps"], "progress.total_steps", minimum=1)
    if step > total:
        raise BadRequest("progress.step must not exceed total_steps")
    return step, total


def _progress_step(snapshot: Mapping[str, Any]) -> int:
    return _progress_pair(snapshot)[0]


def _heartbeat_text(snapshot: Mapping[str, Any]) -> str | None:
    heartbeat = snapshot.get("heartbeat")
    if heartbeat is None:
        return None
    heartbeat = _ensure_keys(heartbeat, "heartbeat", _HEARTBEAT_KEYS)
    text = _require_text(heartbeat["last_heartbeat_utc"], "heartbeat.last_heartbeat_utc")
    _parse_utc(text, "heartbeat.last_heartbeat_utc")
    return text


def _validate_identity_shapes(value: Mapping[str, Any]) -> None:
    display = _ensure_keys(value["display"], "display", _DISPLAY_KEYS)
    _require_text(display["name"], "display.name")
    _require_sha(display["display_sha256"], "display.display_sha256")

    protocol = _ensure_keys(value["protocol"], "protocol", _PROTOCOL_KEYS)
    _require_text(protocol["protocol_id"], "protocol.protocol_id")
    _require_sha(protocol["protocol_sha256"], "protocol.protocol_sha256")

    source = _ensure_keys(value["source"], "source", _SOURCE_REQUIRED_KEYS, _SOURCE_KEYS)
    _require_sha(source["source_sha256"], "source.source_sha256")
    if "git_commit_sha256" in source:
        _require_sha(source["git_commit_sha256"], "source.git_commit_sha256")

    data = _ensure_keys(value["data"], "data", _DATA_REQUIRED_KEYS, _DATA_KEYS)
    _require_sha(data["data_sha256"], "data.data_sha256")
    if "split" in data:
        _require_text(data["split"], "data.split")


def _validate_attempts(value: Any) -> None:
    if not isinstance(value, list):
        raise BadRequest("attempts must be an array")
    seen: set[str] = set()
    for attempt in value:
        attempt = _ensure_keys(attempt, "attempt", _ATTEMPT_REQUIRED_KEYS, _ATTEMPT_KEYS)
        attempt_uid = _require_text(attempt["attempt_uid"], "attempt.attempt_uid")
        if attempt_uid in seen:
            raise BadRequest("attempt_uid values must be unique within a snapshot")
        seen.add(attempt_uid)
        _require_text(attempt["status"], "attempt.status")
        started = _parse_utc(attempt["started_utc"], "attempt.started_utc")
        if "finished_utc" in attempt:
            finished = _parse_utc(attempt["finished_utc"], "attempt.finished_utc")
            if finished < started:
                raise BadRequest("attempt.finished_utc must not be before started_utc")


def _validate_cells(value: Any) -> None:
    if not isinstance(value, list):
        raise BadRequest("cells must be an array")
    seen: set[str] = set()
    for cell in value:
        cell = _ensure_keys(cell, "cell", _CELL_KEYS)
        cell_uid = _require_text(cell["cell_uid"], "cell.cell_uid")
        if cell_uid in seen:
            raise BadRequest("cell_uid values must be unique within a snapshot")
        seen.add(cell_uid)
        _require_optional_text(cell["attempt_uid"], "cell.attempt_uid")
        _require_text(cell["status"], "cell.status")
        _require_int(cell["step"], "cell.step")


def _validate_artifacts(value: Any) -> None:
    if not isinstance(value, list):
        raise BadRequest("artifacts must be an array")
    seen: set[str] = set()
    for artifact in value:
        artifact = _ensure_keys(artifact, "artifact", _ARTIFACT_REQUIRED_KEYS, _ARTIFACT_KEYS)
        artifact_id = _require_text(artifact["artifact_id"], "artifact.artifact_id")
        if artifact_id in seen:
            raise BadRequest("artifact_id values must be unique within a snapshot")
        seen.add(artifact_id)
        _parse_utc(artifact["created_utc"], "artifact.created_utc")
        _require_sha(artifact["sha256"], "artifact.sha256")
        _require_int(artifact["byte_length"], "artifact.byte_length")
        _require_text(artifact["filename"], "artifact.filename")
        for key in ("media_type", "uri", "path"):
            if key in artifact:
                _require_text(artifact[key], f"artifact.{key}")


def _validate_blockers(value: Any) -> None:
    if not isinstance(value, list):
        raise BadRequest("blockers must be an array")
    seen: set[str] = set()
    for blocker in value:
        blocker = _ensure_keys(blocker, "blocker", _BLOCKER_REQUIRED_KEYS, _BLOCKER_KEYS)
        blocker_id = _require_text(blocker["blocker_id"], "blocker.blocker_id")
        if blocker_id in seen:
            raise BadRequest("blocker_id values must be unique within a snapshot")
        seen.add(blocker_id)
        _require_text(blocker["status"], "blocker.status")
        _parse_utc(blocker["created_utc"], "blocker.created_utc")
        _require_text(blocker["message"], "blocker.message")
        if "resolved_utc" in blocker:
            _parse_utc(blocker["resolved_utc"], "blocker.resolved_utc")
        if "severity" in blocker:
            _require_text(blocker["severity"], "blocker.severity")


def _validate_matrix(value: Any, *, terminal: bool) -> None:
    matrix = _ensure_keys(value, "matrix", _MATRIX_KEYS)
    dimensions = _ensure_keys(matrix["dimensions"], "matrix.dimensions", _MATRIX_DIMENSION_KEYS)
    for key in ("seeds", "folds", "variants"):
        _require_text_array(dimensions[key], f"matrix.dimensions.{key}")

    cells = matrix["cells"]
    if not isinstance(cells, list):
        raise BadRequest("matrix.cells must be an array")
    seen_cells: set[str] = set()
    for cell in cells:
        cell = _ensure_keys(cell, "matrix.cell", _MATRIX_CELL_KEYS)
        cell_uid = _require_text(cell["cell_uid"], "matrix.cell.cell_uid")
        if cell_uid in seen_cells:
            raise BadRequest("matrix cell_uid values must be unique within a snapshot")
        seen_cells.add(cell_uid)
        for key in ("seed", "fold", "variant", "state"):
            _require_text(cell[key], f"matrix.cell.{key}")

    _require_text_array(matrix["missing_cell_ids"], "matrix.missing_cell_ids")
    summary = _ensure_keys(matrix["summary"], "matrix.summary", _MATRIX_SUMMARY_KEYS)
    total_cells = _require_int(summary["total_cells"], "matrix.summary.total_cells")
    completed = _require_int(summary["completed"], "matrix.summary.completed")
    failed = _require_int(summary["failed"], "matrix.summary.failed")
    pending = _require_int(summary["pending"], "matrix.summary.pending")
    if completed + failed + pending > total_cells:
        raise BadRequest("matrix.summary counts must not exceed total_cells")
    if not isinstance(matrix["terminal"], bool) or matrix["terminal"] is not terminal:
        raise BadRequest("matrix.terminal must match the run terminal state")


def _ids_by(items: list[Any], id_key: str) -> dict[str, Mapping[str, Any]]:
    return {str(item[id_key]): item for item in items}


def _ensure_monotonic_collection(previous: Mapping[str, Any], current: Mapping[str, Any], field: str, id_key: str, *, immutable_entries: bool = False) -> None:
    previous_by_id = _ids_by(previous[field], id_key)
    current_by_id = _ids_by(current[field], id_key)
    missing = sorted(set(previous_by_id) - set(current_by_id))
    if missing:
        raise BadRequest(f"{field} must not shrink or drop prior ids: {missing}")
    if immutable_entries:
        for item_id, previous_item in previous_by_id.items():
            if current_by_id[item_id] != previous_item:
                raise BadRequest(f"{field} entries are append-only once recorded")


def _validate_transition(previous: Mapping[str, Any], current: Mapping[str, Any]) -> None:
    if previous.get("terminal") is not None:
        raise BadRequest("terminal run is immutable")

    for key in ("schema_version", "run_uid", "display", "protocol", "source", "data", "created_utc"):
        if current[key] != previous[key]:
            raise BadRequest(f"{key} is immutable across run revisions")

    previous_updated = _parse_utc(previous["updated_utc"], "previous.updated_utc")
    current_updated = _parse_utc(current["updated_utc"], "updated_utc")
    if current_updated < previous_updated:
        raise BadRequest("updated_utc must be monotonic")

    previous_step, previous_total = _progress_pair(previous)
    current_step, current_total = _progress_pair(current)
    if current_step < previous_step:
        raise BadRequest("progress.step must be monotonic")
    if current_total < previous_total:
        raise BadRequest("progress.total_steps must be monotonic")

    _ensure_monotonic_collection(previous, current, "attempts", "attempt_uid")
    _ensure_monotonic_collection(previous, current, "cells", "cell_uid")
    _ensure_monotonic_collection(previous, current, "blockers", "blocker_id")
    _ensure_monotonic_collection(previous, current, "artifacts", "artifact_id", immutable_entries=True)

    previous_cells = _ids_by(previous["cells"], "cell_uid")
    for cell_uid, previous_cell in previous_cells.items():
        current_cell = _ids_by(current["cells"], "cell_uid")[cell_uid]
        if _require_int(current_cell["step"], "cell.step") < _require_int(previous_cell["step"], "previous.cell.step"):
            raise BadRequest("cell step must be monotonic")


def _validate_liveness(value: Mapping[str, Any], previous: Mapping[str, Any] | None, *, require_advancing_prior: bool) -> None:
    phase = _require_text(value["phase"], "phase")
    if phase not in PHASE_LIVENESS_MATRIX:
        raise BadRequest("phase has an unknown state")
    terminal = value["terminal"]
    liveness = value["liveness"]
    if terminal is not None and terminal not in TERMINAL_STATES:
        raise BadRequest("terminal must be null, STOPPED, FAILED, or COMPLETED")
    if liveness not in LIVENESS_STATES:
        raise BadRequest("liveness has an unknown state")
    if liveness not in PHASE_LIVENESS_MATRIX[phase]:
        raise BadRequest("liveness is not allowed for phase")

    step, _total = _progress_pair(value)
    heartbeat = _heartbeat_text(value)
    if terminal is None and liveness == "TERMINAL":
        raise BadRequest("TERMINAL liveness requires a terminal state")
    if terminal is not None and liveness != "TERMINAL":
        raise BadRequest("terminal snapshots must use TERMINAL liveness")
    if terminal is None and phase == "RUN_TERMINAL":
        raise BadRequest("RUN_TERMINAL phase requires a terminal state")
    if terminal is not None and phase != "RUN_TERMINAL":
        raise BadRequest("terminal snapshots must use RUN_TERMINAL phase")

    if liveness == "UNKNOWN":
        if step != 0:
            raise BadRequest("UNKNOWN liveness requires zero progress")
        if heartbeat is not None:
            raise BadRequest("UNKNOWN liveness requires no heartbeat")
        return

    if liveness == "TERMINAL":
        if previous is not None and step < _progress_step(previous):
            raise BadRequest("terminal progress must not move backward")
        return

    if previous is None:
        if require_advancing_prior:
            raise BadRequest(f"{liveness} requires a prior snapshot")
        return

    previous_step = _progress_step(previous)
    previous_heartbeat = _heartbeat_text(previous)

    if liveness == "ADVANCING":
        if step <= previous_step:
            raise BadRequest("ADVANCING requires step increase; heartbeat alone is insufficient")
        return

    if liveness == "STALLED":
        if step != previous_step:
            raise BadRequest("STALLED requires unchanged progress")
        if heartbeat is None:
            raise BadRequest("STALLED requires a new heartbeat without progress")
        if previous_heartbeat is not None:
            current_heartbeat = _parse_utc(heartbeat, "heartbeat.last_heartbeat_utc")
            prior_heartbeat = _parse_utc(previous_heartbeat, "previous.heartbeat.last_heartbeat_utc")
            if current_heartbeat <= prior_heartbeat:
                raise BadRequest("STALLED requires a newer heartbeat without progress")
        return


def _validate_snapshot(snapshot: Mapping[str, Any], previous: Mapping[str, Any] | None = None, *, require_advancing_prior: bool = True) -> dict[str, Any]:
    value = _clone_canonical(snapshot)
    _validate_number_bounds(value)
    _ensure_keys(value, "run snapshot", RUN_SNAPSHOT_REQUIRED_KEYS)
    if value["schema_version"] != RUN_STATE_SCHEMA:
        raise BadRequest("run snapshot schema_version mismatch")

    _require_text(value["run_uid"], "run_uid")
    _require_int(value["run_revision"], "run_revision", minimum=1)
    created = _parse_utc(value["created_utc"], "created_utc")
    updated = _parse_utc(value["updated_utc"], "updated_utc")
    if updated < created:
        raise BadRequest("updated_utc must not be before created_utc")

    _validate_identity_shapes(value)
    _validate_attempts(value["attempts"])
    _validate_cells(value["cells"])
    _validate_blockers(value["blockers"])
    _validate_artifacts(value["artifacts"])
    if value["locks"] != SIX_FALSE_LOCKS:
        raise BadRequest("snapshot locks must be the canonical six false locks")
    _validate_liveness(value, previous, require_advancing_prior=require_advancing_prior)
    _validate_matrix(value["matrix"], terminal=value["terminal"] is not None)

    heartbeat = _heartbeat_text(value)
    if heartbeat is not None and _parse_utc(heartbeat, "heartbeat.last_heartbeat_utc") > updated:
        raise BadRequest("heartbeat.last_heartbeat_utc must not be after updated_utc")
    if previous is not None:
        _validate_transition(previous, value)
    return value


def _record_object(
    *,
    registry_epoch: str,
    global_seq: int,
    run_uid: str,
    run_revision: int,
    attempt_uid: str | None,
    cell_uid: str | None,
    event_type: str,
    payload_sha256: str,
    previous_global_hash: str,
    created_utc: str,
) -> dict[str, Any]:
    return {
        "schema_version": REGISTRY_RECORD_SCHEMA,
        "registry_epoch": registry_epoch,
        "global_seq": global_seq,
        "run_uid": run_uid,
        "run_revision": run_revision,
        "attempt_uid": attempt_uid,
        "cell_uid": cell_uid,
        "event_type": event_type,
        "payload_sha256": payload_sha256,
        "previous_global_hash": previous_global_hash,
        "created_utc": created_utc,
    }


class KronosV5Registry:
    """Small explicit registry API for V5 backend readers and producers."""

    def __init__(self, path: str | Path, *, cursor_keys: Mapping[str, bytes] | None = None, now: NowSource | datetime | str | None = None) -> None:
        self.path = Path(path)
        self._now = now
        self._lock = threading.RLock()
        self._read_only = False
        self._corrupt_reason: str | None = None
        if cursor_keys is None:
            self._cursor_keys = {DEFAULT_CURSOR_KEY_ID: secrets.token_bytes(32)}
        else:
            self._cursor_keys = self._normalize_cursor_keys(cursor_keys)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = sqlite3.connect(str(self.path), timeout=30.0, isolation_level=None, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._configure_connection()
            self._ensure_schema()
            self._meta = self._load_meta()
            self._verify_startup()
        except sqlite3.DatabaseError as exc:
            raise Unavailable(f"registry SQLite database is unavailable: {exc}") from exc

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "KronosV5Registry":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.close()

    @staticmethod
    def _normalize_cursor_keys(cursor_keys: Mapping[str, bytes]) -> dict[str, bytes]:
        if not isinstance(cursor_keys, Mapping) or not cursor_keys:
            raise BadRequest("cursor_keys must be a non-empty mapping")
        normalized: dict[str, bytes] = {}
        for key_id, key in cursor_keys.items():
            if not isinstance(key_id, str) or not key_id:
                raise BadRequest("cursor key id must be a non-empty string")
            if not isinstance(key, bytes) or not key:
                raise BadRequest("cursor key material must be non-empty bytes")
            normalized[key_id] = bytes(key)
        return normalized

    def _now_utc(self) -> datetime:
        source = self._now() if callable(self._now) else self._now
        if source is None:
            return datetime.now(timezone.utc)
        if isinstance(source, str):
            return _parse_utc(source, "now")
        if isinstance(source, datetime):
            if source.tzinfo is None:
                raise BadRequest("now datetime must be timezone-aware")
            return source.astimezone(timezone.utc)
        raise BadRequest("now must be a datetime, canonical UTC string, callable, or None")

    def _now_text(self) -> str:
        return _format_utc(self._now_utc())

    def _configure_connection(self) -> None:
        self._conn.execute("PRAGMA busy_timeout=30000")
        journal_mode = str(self._conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
        if journal_mode != "wal":
            raise Unavailable("registry requires SQLite WAL journal mode")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def _ensure_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS registry_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                schema TEXT NOT NULL,
                registry_epoch TEXT NOT NULL,
                genesis_global_hash TEXT NOT NULL,
                created_utc TEXT NOT NULL,
                cursor_key_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS journal (
                global_seq INTEGER PRIMARY KEY AUTOINCREMENT,
                run_uid TEXT NOT NULL,
                run_revision INTEGER NOT NULL,
                attempt_uid TEXT,
                cell_uid TEXT,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                previous_global_hash TEXT NOT NULL,
                record_json TEXT NOT NULL,
                record_hash TEXT NOT NULL,
                record_bytes BLOB NOT NULL,
                created_utc TEXT NOT NULL,
                UNIQUE (run_uid, run_revision)
            );
            CREATE TABLE IF NOT EXISTS current_runs (
                run_uid TEXT PRIMARY KEY,
                run_revision INTEGER NOT NULL,
                global_seq INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                record_hash TEXT NOT NULL,
                updated_utc TEXT NOT NULL,
                FOREIGN KEY (global_seq) REFERENCES journal(global_seq)
            );
            CREATE INDEX IF NOT EXISTS idx_journal_run_revision ON journal(run_uid, run_revision);
            CREATE INDEX IF NOT EXISTS idx_journal_run_global ON journal(run_uid, global_seq);
            """
        )
        count = int(self._conn.execute("SELECT COUNT(*) FROM registry_meta").fetchone()[0])
        if count == 0:
            cursor_key_id = next(iter(self._cursor_keys), DEFAULT_CURSOR_KEY_ID)
            self._conn.execute(
                "INSERT INTO registry_meta(id, schema, registry_epoch, genesis_global_hash, created_utc, cursor_key_id) VALUES (1, ?, ?, ?, ?, ?)",
                (REGISTRY_SCHEMA, str(uuid.uuid4()), ZERO_SHA256, self._now_text(), cursor_key_id),
            )
        elif count != 1:
            self._mark_corrupt("registry_meta must contain exactly one row")

    def _load_meta(self) -> dict[str, Any]:
        row = self._conn.execute("SELECT schema, registry_epoch, genesis_global_hash, created_utc, cursor_key_id FROM registry_meta WHERE id=1").fetchone()
        if row is None:
            self._mark_corrupt("registry_meta row is missing")
            return {
                "schema": REGISTRY_SCHEMA,
                "registry_epoch": "00000000-0000-4000-8000-000000000000",
                "genesis_global_hash": ZERO_SHA256,
                "created_utc": self._now_text(),
                "cursor_key_id": DEFAULT_CURSOR_KEY_ID,
            }
        meta = dict(row)
        if meta["schema"] != REGISTRY_SCHEMA:
            self._mark_corrupt("registry_meta schema mismatch")
        if not isinstance(meta["registry_epoch"], str) or not _UUID4_RE.fullmatch(meta["registry_epoch"]):
            self._mark_corrupt("registry_epoch must be a UUIDv4")
        if meta["genesis_global_hash"] != ZERO_SHA256:
            self._mark_corrupt("genesis_global_hash must be 64 zeros")
        try:
            _parse_utc(meta["created_utc"], "registry_meta.created_utc")
        except BadRequest as exc:
            self._mark_corrupt(str(exc))
        if not isinstance(meta["cursor_key_id"], str) or not meta["cursor_key_id"]:
            self._mark_corrupt("cursor_key_id must be fixed and non-empty")
        return meta

    def _mark_corrupt(self, reason: str) -> None:
        self._read_only = True
        if self._corrupt_reason is None:
            self._corrupt_reason = reason
        try:
            self._conn.execute("PRAGMA query_only=ON")
        except sqlite3.DatabaseError:
            pass

    def _verify_startup(self) -> None:
        if self._read_only:
            return
        try:
            fk_rows = self._conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk_rows:
                self._mark_corrupt("SQLite foreign_key_check failed")
                return
            self._verify_journal_chain()
            if not self._read_only:
                self._verify_current_heads()
        except (BadRequest, sqlite3.DatabaseError) as exc:
            self._mark_corrupt(str(exc))

    def _verify_journal_chain(self) -> None:
        expected_seq = 1
        previous_hash = self._meta["genesis_global_hash"]
        per_run_revision: dict[str, int] = {}
        per_run_snapshot: dict[str, dict[str, Any]] = {}
        previous_created_utc: str | None = None
        rows = self._conn.execute("SELECT * FROM journal ORDER BY global_seq ASC").fetchall()
        for row in rows:
            seq = int(row["global_seq"])
            if seq != expected_seq:
                self._mark_corrupt("global sequence gap")
                return
            if row["previous_global_hash"] != previous_hash:
                self._mark_corrupt("global hash fork")
                return
            payload_bytes = row["payload_json"].encode("utf-8")
            try:
                snapshot = json.loads(payload_bytes)
            except json.JSONDecodeError:
                self._mark_corrupt("payload_json is not JSON")
                return
            if canonical_bytes(snapshot) != payload_bytes:
                self._mark_corrupt("payload_json is not canonical JCS")
                return
            if sha256_hex(payload_bytes) != row["payload_sha256"]:
                self._mark_corrupt("payload_sha256 mismatch")
                return
            if snapshot.get("run_uid") != row["run_uid"] or snapshot.get("run_revision") != row["run_revision"]:
                self._mark_corrupt("journal row does not match snapshot identity")
                return
            expected_revision = per_run_revision.get(row["run_uid"], 0) + 1
            if row["run_revision"] != expected_revision:
                self._mark_corrupt("per-run revision gap or fork")
                return
            try:
                validated_snapshot = _validate_snapshot(snapshot, per_run_snapshot.get(row["run_uid"]))
            except BadRequest as exc:
                self._mark_corrupt(f"semantic validation failed: {exc}")
                return
            try:
                _ensure_record_created_after(previous_created_utc, row["created_utc"], "journal.created_utc")
            except BadRequest as exc:
                self._mark_corrupt(str(exc))
                return
            record = _record_object(
                registry_epoch=self._meta["registry_epoch"],
                global_seq=seq,
                run_uid=row["run_uid"],
                run_revision=row["run_revision"],
                attempt_uid=row["attempt_uid"],
                cell_uid=row["cell_uid"],
                event_type=row["event_type"],
                payload_sha256=row["payload_sha256"],
                previous_global_hash=row["previous_global_hash"],
                created_utc=row["created_utc"],
            )
            record_json = canonical_bytes(record)
            record_bytes = RECORD_DOMAIN + record_json
            if row["record_json"].encode("utf-8") != record_json or bytes(row["record_bytes"]) != record_bytes:
                self._mark_corrupt("record bytes mismatch")
                return
            if sha256_hex(record_bytes) != row["record_hash"]:
                self._mark_corrupt("record_hash mismatch")
                return
            per_run_revision[row["run_uid"]] = row["run_revision"]
            per_run_snapshot[row["run_uid"]] = validated_snapshot
            previous_hash = row["record_hash"]
            previous_created_utc = row["created_utc"]
            expected_seq += 1

    def _verify_current_heads(self) -> None:
        expected = {
            row["run_uid"]: row
            for row in self._conn.execute(
                """
                SELECT j.* FROM journal j
                JOIN (SELECT run_uid, MAX(run_revision) AS run_revision FROM journal GROUP BY run_uid) latest
                  ON latest.run_uid = j.run_uid AND latest.run_revision = j.run_revision
                ORDER BY j.run_uid ASC
                """
            ).fetchall()
        }
        current = {row["run_uid"]: row for row in self._conn.execute("SELECT * FROM current_runs ORDER BY run_uid ASC").fetchall()}
        if set(expected) != set(current):
            self._mark_corrupt("current_runs torn tail")
            return
        for run_uid, row in expected.items():
            head = current[run_uid]
            if (
                head["run_revision"] != row["run_revision"]
                or head["global_seq"] != row["global_seq"]
                or head["payload_json"] != row["payload_json"]
                or head["payload_sha256"] != row["payload_sha256"]
                or head["record_hash"] != row["record_hash"]
            ):
                self._mark_corrupt("current_runs head does not match journal")
                return

    def _ensure_writable(self) -> None:
        if self._read_only:
            raise Corrupt(self._corrupt_reason or "REGISTRY_CORRUPT")

    def _ensure_readable(self) -> None:
        if self._read_only:
            raise Corrupt(self._corrupt_reason or "REGISTRY_CORRUPT")

    def _latest_record_identity(self) -> tuple[int, str, str | None]:
        row = self._conn.execute("SELECT global_seq, record_hash, created_utc FROM journal ORDER BY global_seq DESC LIMIT 1").fetchone()
        if row is None:
            return 0, self._meta["genesis_global_hash"], None
        return int(row["global_seq"]), str(row["record_hash"]), str(row["created_utc"])

    def _latest_identity_pair(self) -> tuple[int, str]:
        latest_seq, latest_hash, _created_utc = self._latest_record_identity()
        return latest_seq, latest_hash

    def identity(self) -> RegistryIdentity:
        with self._lock:
            latest_seq, latest_hash = self._latest_identity_pair()
            return RegistryIdentity(
                schema=self._meta["schema"],
                registry_epoch=self._meta["registry_epoch"],
                genesis_global_hash=self._meta["genesis_global_hash"],
                cursor_key_id=self._meta["cursor_key_id"],
                created_utc=self._meta["created_utc"],
                read_only=self._read_only,
                corrupt_reason=self._corrupt_reason,
                latest_global_seq=latest_seq,
                latest_record_hash=latest_hash,
            )

    def append_snapshot(
        self,
        snapshot: Mapping[str, Any],
        *,
        expected_run_revision: int,
        event_type: str,
        attempt_uid: str | None = None,
        cell_uid: str | None = None,
        created_utc: str | None = None,
    ) -> SnapshotRead:
        """Append one complete run snapshot using BEGIN IMMEDIATE and per-run CAS."""

        self._ensure_writable()
        if not isinstance(expected_run_revision, int) or isinstance(expected_run_revision, bool) or expected_run_revision < 0:
            raise BadRequest("expected_run_revision must be an explicit non-negative integer")
        event_type = _require_text(event_type, "event_type")
        if attempt_uid is not None:
            _require_text(attempt_uid, "attempt_uid")
        if cell_uid is not None:
            _require_text(cell_uid, "cell_uid")
        created = created_utc or self._now_text()
        _parse_utc(created, "created_utc")
        initial = _validate_snapshot(snapshot, require_advancing_prior=False)
        run_uid = initial["run_uid"]
        run_revision = initial["run_revision"]

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                current = self._conn.execute("SELECT * FROM current_runs WHERE run_uid=?", (run_uid,)).fetchone()
                current_revision = int(current["run_revision"]) if current is not None else 0
                if expected_run_revision != current_revision:
                    raise Conflict("expected_run_revision CAS mismatch")
                if run_revision != current_revision + 1:
                    raise Conflict("run_revision must advance by exactly one")
                previous_snapshot = json.loads(current["payload_json"]) if current is not None else None
                if previous_snapshot is not None and previous_snapshot.get("terminal") is not None:
                    raise Conflict("terminal run is immutable")
                value = _validate_snapshot(initial, previous_snapshot)
                payload = canonical_bytes(value)
                payload_sha = sha256_hex(payload)
                latest_seq, previous_hash, previous_created_utc = self._latest_record_identity()
                _ensure_record_created_after(previous_created_utc, created)
                global_seq = latest_seq + 1
                record = _record_object(
                    registry_epoch=self._meta["registry_epoch"],
                    global_seq=global_seq,
                    run_uid=run_uid,
                    run_revision=run_revision,
                    attempt_uid=attempt_uid,
                    cell_uid=cell_uid,
                    event_type=event_type,
                    payload_sha256=payload_sha,
                    previous_global_hash=previous_hash,
                    created_utc=created,
                )
                record_json = canonical_bytes(record)
                record_blob = RECORD_DOMAIN + record_json
                record_sha = sha256_hex(record_blob)
                self._conn.execute(
                    """
                    INSERT INTO journal(global_seq, run_uid, run_revision, attempt_uid, cell_uid, event_type, payload_json, payload_sha256, previous_global_hash, record_json, record_hash, record_bytes, created_utc)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        global_seq,
                        run_uid,
                        run_revision,
                        attempt_uid,
                        cell_uid,
                        event_type,
                        payload.decode("utf-8"),
                        payload_sha,
                        previous_hash,
                        record_json.decode("utf-8"),
                        record_sha,
                        record_blob,
                        created,
                    ),
                )
                self._conn.execute(
                    """
                    INSERT INTO current_runs(run_uid, run_revision, global_seq, payload_json, payload_sha256, record_hash, updated_utc)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_uid) DO UPDATE SET
                        run_revision=excluded.run_revision,
                        global_seq=excluded.global_seq,
                        payload_json=excluded.payload_json,
                        payload_sha256=excluded.payload_sha256,
                        record_hash=excluded.record_hash,
                        updated_utc=excluded.updated_utc
                    """,
                    (run_uid, run_revision, global_seq, payload.decode("utf-8"), payload_sha, record_sha, created),
                )
                self._conn.execute("COMMIT")
                return SnapshotRead(
                    run_uid=run_uid,
                    run_revision=run_revision,
                    global_seq=global_seq,
                    payload_sha256=payload_sha,
                    record_hash=record_sha,
                    created_utc=created,
                    snapshot=deepcopy(value),
                    snapshot_global_seq=global_seq,
                )
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    write_snapshot = append_snapshot

    def _row_to_read(self, row: sqlite3.Row, snapshot_global_seq: int | None = None) -> SnapshotRead:
        return SnapshotRead(
            run_uid=row["run_uid"],
            run_revision=int(row["run_revision"]),
            global_seq=int(row["global_seq"]),
            payload_sha256=row["payload_sha256"],
            record_hash=row["record_hash"],
            created_utc=row["created_utc"],
            snapshot=json.loads(row["payload_json"]),
            snapshot_global_seq=snapshot_global_seq,
        )

    def _query_hash(self, *, limit: int, filters: Mapping[str, Any] | None, sort: str) -> str:
        normalized_filters = _clone_canonical(filters or {})
        if not isinstance(normalized_filters, dict):
            raise BadRequest("filters must be an object")
        return sha256_hex(canonical_bytes({"limit": limit, "filters": normalized_filters, "sort": sort}))

    def _active_cursor_key(self) -> bytes:
        key_id = self._meta["cursor_key_id"]
        key = self._cursor_keys.get(key_id)
        if key is None:
            raise Unavailable("active cursor key is unavailable")
        return key

    def _encode_cursor(self, payload: Mapping[str, Any]) -> str:
        body = canonical_bytes(payload)
        signature = hmac.new(self._active_cursor_key(), body, hashlib.sha256).digest()
        return f"{_b64url(body)}.{_b64url(signature)}"

    def _decode_cursor(self, token: str, *, query_sha256: str) -> dict[str, Any]:
        if not isinstance(token, str) or token.count(".") != 1:
            raise BadRequest("cursor must be a signed base64url envelope")
        body_part, signature_part = token.split(".")
        body = _decode_b64url(body_part, "cursor payload")
        signature = _decode_b64url(signature_part, "cursor signature")
        if len(signature) != hashlib.sha256().digest_size:
            raise BadRequest("cursor signature length is invalid")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise BadRequest("cursor payload is not JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _CURSOR_KEYS or canonical_bytes(payload) != body:
            raise BadRequest("cursor payload is not canonical")
        if payload["schema"] != CURSOR_SCHEMA:
            raise BadRequest("cursor schema mismatch")
        key_id = payload["key_id"]
        if key_id != self._meta["cursor_key_id"] or key_id not in self._cursor_keys:
            raise Gone("cursor key is no longer active")
        expected = hmac.new(self._cursor_keys[key_id], body, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise BadRequest("cursor signature is invalid")
        if payload["registry_epoch"] != self._meta["registry_epoch"]:
            raise Gone("cursor registry_epoch is stale")
        if payload["query_sha256"] != query_sha256:
            raise BadRequest("cursor query does not match request")
        issued = _parse_utc(payload["issued_at"], "cursor.issued_at")
        expires = _parse_utc(payload["expires_at"], "cursor.expires_at")
        if expires <= issued or self._now_utc() >= expires:
            raise Gone("cursor has expired")
        for name in ("snapshot_global_seq", "last_global_seq"):
            _require_int(payload[name], f"cursor.{name}")
        _require_text(payload["last_run_uid"], "cursor.last_run_uid")
        return payload

    def _latest_rows_at_snapshot(self, snapshot_global_seq: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT j.* FROM journal j
            JOIN (
                SELECT run_uid, MAX(global_seq) AS global_seq
                FROM journal
                WHERE global_seq <= ?
                GROUP BY run_uid
            ) latest ON latest.run_uid = j.run_uid AND latest.global_seq = j.global_seq
            ORDER BY j.global_seq DESC, j.run_uid ASC
            """,
            (snapshot_global_seq,),
        ).fetchall()

    @staticmethod
    def _matches_filters(snapshot: Mapping[str, Any], filters: Mapping[str, Any] | None) -> bool:
        if not filters:
            return True
        for key, expected in filters.items():
            if not isinstance(key, str) or _json_path(snapshot, key) != expected:
                return False
        return True

    def list_runs(self, *, limit: int = 50, cursor: str | None = None, filters: Mapping[str, Any] | None = None, sort: str = "latest_desc") -> Page:
        self._ensure_readable()
        if sort != "latest_desc":
            raise BadRequest("only latest_desc registry order is supported")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIST_LIMIT:
            raise BadRequest("limit must be in 1..100")
        query_sha = self._query_hash(limit=limit, filters=filters, sort=sort)

        with self._lock:
            self._conn.execute("BEGIN")
            try:
                if cursor is None:
                    snapshot_global_seq, _ = self._latest_identity_pair()
                    issued_at = self._now_text()
                    expires_at = _format_utc(_parse_utc(issued_at, "issued_at") + CURSOR_TTL)
                    last_global_seq: int | None = None
                    last_run_uid: str | None = None
                else:
                    payload = self._decode_cursor(cursor, query_sha256=query_sha)
                    snapshot_global_seq = int(payload["snapshot_global_seq"])
                    issued_at = payload["issued_at"]
                    expires_at = payload["expires_at"]
                    last_global_seq = int(payload["last_global_seq"])
                    last_run_uid = str(payload["last_run_uid"])

                reads: list[SnapshotRead] = []
                for row in self._latest_rows_at_snapshot(snapshot_global_seq):
                    if last_global_seq is not None and not (row["global_seq"] < last_global_seq or (row["global_seq"] == last_global_seq and row["run_uid"] > last_run_uid)):
                        continue
                    read = self._row_to_read(row, snapshot_global_seq)
                    if self._matches_filters(read.snapshot, filters):
                        reads.append(read)
                    if len(reads) > limit:
                        break
                emitted = tuple(reads[:limit])
                if len(reads) > limit and emitted:
                    last = emitted[-1]
                    next_cursor = self._encode_cursor(
                        {
                            "schema": CURSOR_SCHEMA,
                            "registry_epoch": self._meta["registry_epoch"],
                            "snapshot_global_seq": snapshot_global_seq,
                            "last_global_seq": last.global_seq,
                            "last_run_uid": last.run_uid,
                            "query_sha256": query_sha,
                            "issued_at": issued_at,
                            "expires_at": expires_at,
                            "key_id": self._meta["cursor_key_id"],
                        }
                    )
                else:
                    next_cursor = None
                self._conn.execute("COMMIT")
                return Page(
                    items=emitted,
                    next_cursor=next_cursor,
                    snapshot_global_seq=snapshot_global_seq,
                    registry_epoch=self._meta["registry_epoch"],
                    issued_at=issued_at,
                    expires_at=expires_at,
                )
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def get_run(self, run_uid: str, *, revision: int) -> SnapshotRead:
        self._ensure_readable()
        _require_text(run_uid, "run_uid")
        _require_int(revision, "revision", minimum=1)
        with self._lock:
            row = self._conn.execute("SELECT * FROM journal WHERE run_uid=? AND run_revision=?", (run_uid, revision)).fetchone()
        if row is None:
            raise NotFound("run revision not found")
        return self._row_to_read(row, int(row["global_seq"]))

    def list_events(
        self,
        run_uid: str,
        *,
        revision: int,
        attempt_uid: str | None = None,
        after_global_seq: int = 0,
        limit: int = MAX_EVENTS_LIMIT,
    ) -> EventsPage:
        self._ensure_readable()
        _require_text(run_uid, "run_uid")
        _require_int(revision, "revision", minimum=1)
        _require_int(after_global_seq, "after_global_seq")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_EVENTS_LIMIT:
            raise BadRequest("events limit must be in 1..500")
        if attempt_uid is not None:
            _require_text(attempt_uid, "attempt_uid")
        target = self.get_run(run_uid, revision=revision)
        with self._lock:
            if attempt_uid is None:
                rows = self._conn.execute(
                    """
                    SELECT * FROM journal
                    WHERE run_uid=? AND run_revision<=? AND global_seq>?
                    ORDER BY global_seq ASC
                    LIMIT ?
                    """,
                    (run_uid, revision, after_global_seq, limit + 1),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """
                    SELECT * FROM journal
                    WHERE run_uid=? AND run_revision<=? AND global_seq>? AND attempt_uid=?
                    ORDER BY global_seq ASC
                    LIMIT ?
                    """,
                    (run_uid, revision, after_global_seq, attempt_uid, limit + 1),
                ).fetchall()
        emitted_rows = rows[:limit]
        items = tuple(self._row_to_event(row) for row in emitted_rows)
        next_after = int(emitted_rows[-1]["global_seq"]) if len(rows) > limit and emitted_rows else None
        return EventsPage(items=items, next_after_global_seq=next_after, snapshot_global_seq=target.global_seq, run_uid=run_uid, run_revision=revision)

    def _row_to_event(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "global_seq": int(row["global_seq"]),
            "run_uid": row["run_uid"],
            "run_revision": int(row["run_revision"]),
            "attempt_uid": row["attempt_uid"],
            "cell_uid": row["cell_uid"],
            "event_type": row["event_type"],
            "payload_sha256": row["payload_sha256"],
            "previous_global_hash": row["previous_global_hash"],
            "record_hash": row["record_hash"],
            "created_utc": row["created_utc"],
            "snapshot": json.loads(row["payload_json"]),
        }

    def get_matrix(self, run_uid: str, *, revision: int) -> MatrixRead:
        read = self.get_run(run_uid, revision=revision)
        matrix = read.snapshot.get("matrix")
        if not isinstance(matrix, dict):
            raise BadRequest("snapshot matrix is unavailable")
        return MatrixRead(
            run_uid=run_uid,
            run_revision=revision,
            global_seq=read.global_seq,
            snapshot_global_seq=read.global_seq,
            matrix=deepcopy(matrix),
        )

    def list_artifacts(self, run_uid: str, *, revision: int) -> list[dict[str, Any]]:
        read = self.get_run(run_uid, revision=revision)
        artifacts = read.snapshot.get("artifacts")
        if not isinstance(artifacts, list):
            raise BadRequest("snapshot artifacts are unavailable")
        if len(artifacts) > MAX_ARTIFACTS:
            raise TooLarge("artifact collection exceeds V5 limit")
        return [deepcopy(artifact) for artifact in sorted(artifacts, key=lambda item: item["artifact_id"])]

    def get_artifact(self, run_uid: str, artifact_id: str, *, revision: int) -> dict[str, Any]:
        _require_text(artifact_id, "artifact_id")
        for artifact in self.list_artifacts(run_uid, revision=revision):
            if artifact["artifact_id"] == artifact_id:
                return artifact
        raise NotFound("artifact not found")


__all__ = [
    "BadRequest",
    "Conflict",
    "Corrupt",
    "CURSOR_SCHEMA",
    "DEFAULT_CURSOR_KEY_ID",
    "EventsPage",
    "Gone",
    "KronosV5Registry",
    "MatrixRead",
    "NotFound",
    "Page",
    "RECORD_DOMAIN",
    "REGISTRY_RECORD_SCHEMA",
    "REGISTRY_SCHEMA",
    "RUN_STATE_SCHEMA",
    "RegistryBadRequest",
    "RegistryConflict",
    "RegistryCorrupt",
    "RegistryError",
    "RegistryGone",
    "RegistryIdentity",
    "RegistryNotFound",
    "RegistryTooLarge",
    "RegistryUnavailable",
    "SIX_FALSE_LOCKS",
    "SnapshotRead",
    "TooLarge",
    "Unavailable",
    "ZERO_SHA256",
    "canonical_bytes",
    "registry_record_bytes",
    "registry_record_hash",
    "sha256_hex",
]
