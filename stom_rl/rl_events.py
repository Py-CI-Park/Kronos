"""JSONL event helpers for realtime STOM reinforcement-learning views."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


SCHEMA_VERSION = "stom_rl_live_event.v1"
ACTION_LABELS = {0: "hold", 1: "buy", 2: "sell"}
MAX_EVENT_LIMIT = 10_000


def utc_now_iso() -> str:
    """Return a compact timezone-aware UTC timestamp."""

    return datetime.now(tz=timezone.utc).isoformat()


def clean_json_value(value: Any) -> Any:
    """Convert numpy/scalar values to JSON-safe values and drop NaN/inf."""

    if value is None:
        return None
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if hasattr(value, "item"):
        return clean_json_value(value.item())
    if isinstance(value, Mapping):
        return {str(k): clean_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json_value(v) for v in value]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return number if math.isfinite(number) else None


def action_label(action: Any) -> str:
    """Return a stable label for a STOM discrete action."""

    try:
        return ACTION_LABELS.get(int(action), str(action))
    except (TypeError, ValueError):
        return str(action)


@dataclass(frozen=True)
class RlLiveEvent:
    """Single JSONL event consumed by the realtime RL dashboard."""

    run_id: str
    algorithm: str
    phase: str
    global_step: int
    action: Optional[int] = None
    reward: Optional[float] = None
    episode: Optional[int] = None
    episode_id: Optional[str] = None
    timestamp: Optional[str] = None
    price: Optional[float] = None
    position: Optional[float] = None
    equity: Optional[float] = None
    loss: Optional[float] = None
    exploration: Optional[float] = None
    source: str = "sb3_smoke"
    schema_version: str = SCHEMA_VERSION
    timestamp_utc: str = field(default_factory=utc_now_iso)
    info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["action_name"] = action_label(self.action) if self.action is not None else None
        return {key: clean_json_value(value) for key, value in payload.items()}


class RlLiveEventWriter:
    """Append-only JSONL writer for RL live events."""

    def __init__(self, path: str | Path, *, run_id: str, enabled: bool = True):
        self.path = Path(path)
        self.run_id = str(run_id)
        self.enabled = bool(enabled)

    def reset(self) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def write(self, event: RlLiveEvent | Mapping[str, Any]) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = event.to_dict() if isinstance(event, RlLiveEvent) else clean_json_value(dict(event))
        with self.path.open("a", encoding="utf-8", newline="") as f:
            f.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")

    def write_step(self, *, algorithm: str, phase: str, global_step: int, **kwargs: Any) -> None:
        self.write(
            RlLiveEvent(
                run_id=self.run_id,
                algorithm=str(algorithm),
                phase=str(phase),
                global_step=int(global_step),
                **kwargs,
            )
        )


def read_live_events(path: str | Path, *, limit: int = 500, tail: bool = True) -> Tuple[List[Dict[str, Any]], bool]:
    """Read JSONL events with a bounded limit and malformed-line tolerance."""

    path = Path(path)
    limit = max(0, min(int(limit), MAX_EVENT_LIMIT))
    if not path.is_file() or limit == 0:
        return [], False
    lines = path.read_text(encoding="utf-8").splitlines()
    truncated = len(lines) > limit
    source = reversed(lines) if tail else iter(lines)
    rows: List[Dict[str, Any]] = []
    for line in source:
        if len(rows) >= limit:
            break
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    if tail:
        rows.reverse()
    return rows, truncated


def summarize_live_events(events: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    rows = list(events)
    phases = Counter(str(row.get("phase") or "unknown") for row in rows)
    algorithms = Counter(str(row.get("algorithm") or "unknown") for row in rows)
    actions = Counter(str(row.get("action_name") or action_label(row.get("action"))) for row in rows)
    rewards = [float(row["reward"]) for row in rows if row.get("reward") is not None]
    equities = [float(row["equity"]) for row in rows if row.get("equity") is not None]
    latest = rows[-1] if rows else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "event_count": len(rows),
        "phases": dict(sorted(phases.items())),
        "algorithms": dict(sorted(algorithms.items())),
        "actions": dict(sorted(actions.items())),
        "avg_reward": sum(rewards) / len(rewards) if rewards else 0.0,
        "latest_equity": equities[-1] if equities else None,
        "latest_event": dict(latest),
    }


def summarize_live_event_file(path: str | Path, *, limit: int = MAX_EVENT_LIMIT) -> Dict[str, Any]:
    rows, truncated = read_live_events(path, limit=limit, tail=False)
    summary = summarize_live_events(rows)
    summary["truncated"] = truncated
    return summary


# ---------------------------------------------------------------------------
# Additive metric / action-availability / freshness contract.
#
# SCHEMA_VERSION ("stom_rl_live_event.v1") is intentionally UNCHANGED: none of
# the following adds a required event column. Truthful metric/action metadata
# rides inside the existing additive ``info`` dict (per event) and/or run-level
# defaults (for archived artifacts that predate this contract). Unknown values
# stay ``None`` so consumers render NOT_RECORDED rather than coercing to
# zero / HOLD / percent.
# ---------------------------------------------------------------------------

# Run lifecycle statuses. NOTE: "LIVE" is NOT a status; it is a derived boolean
# meaning ``status == RUNNING`` (an explicitly running producer whose event
# file/step advanced within two poll intervals). Polling alone is never LIVE.
RUN_STATUS_RUNNING = "RUNNING"
RUN_STATUS_COMPLETED = "COMPLETED"
RUN_STATUS_STALE = "STALE"
RUN_STATUS_REPLAY = "REPLAY"
RUN_STATUS_IDLE = "IDLE"
RUN_STATUS_MISSING = "MISSING"
RUN_STATUSES = (
    RUN_STATUS_RUNNING,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_STALE,
    RUN_STATUS_REPLAY,
    RUN_STATUS_IDLE,
    RUN_STATUS_MISSING,
)

# Declared metric vocabularies. Producers declare truthfully; consumers never
# infer a kind/unit that was not declared.
REWARD_KINDS = (
    "raw_reward",
    "return_fraction",
    "return_percent",
    "nav_delta",
    "cumulative_pnl",
)
EQUITY_KINDS = (
    "normalized_nav",
    "krw_nav",
    "cumulative_pnl",
    "raw_equity",
)
METRIC_UNITS = ("score", "fraction", "percent", "krw", "normalized", "unknown")

METRIC_METADATA_KEYS = (
    "reward_kind",
    "reward_unit",
    "equity_kind",
    "equity_unit",
    "action_recorded",
)

ACTION_RECORDED = "RECORDED"
ACTION_NOT_RECORDED = "NOT_RECORDED"


def default_run_metric_metadata() -> Dict[str, Any]:
    """Conservative run-level metric defaults: everything unknown stays ``None``."""

    return {key: None for key in METRIC_METADATA_KEYS}


def resolve_event_metric_metadata(
    event: Mapping[str, Any],
    run_defaults: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge per-event ``info`` metadata over run-level defaults.

    Precedence: per-event ``info`` > run-level defaults > ``None``. A value is
    only overridden when it is explicitly declared (non-None); unknown stays
    ``None`` so callers render NOT_RECORDED instead of coercing.
    """

    meta = default_run_metric_metadata()
    if isinstance(run_defaults, Mapping):
        for key in METRIC_METADATA_KEYS:
            if run_defaults.get(key) is not None:
                meta[key] = run_defaults[key]
    info = event.get("info") if isinstance(event, Mapping) else None
    if isinstance(info, Mapping):
        for key in METRIC_METADATA_KEYS:
            if info.get(key) is not None:
                meta[key] = info[key]
    return meta


def action_availability(event: Mapping[str, Any]) -> str:
    """Return ``RECORDED`` or ``NOT_RECORDED`` without coercing null to HOLD/0."""

    if not isinstance(event, Mapping):
        return ACTION_NOT_RECORDED
    info = event.get("info")
    if isinstance(info, Mapping):
        recorded = info.get("action_recorded")
        if recorded is True:
            return ACTION_RECORDED
        if recorded is False:
            return ACTION_NOT_RECORDED
    # No declared availability: fall back to a real action value only; never
    # treat a missing/None action as a HOLD.
    return ACTION_RECORDED if event.get("action") is not None else ACTION_NOT_RECORDED


def metrics_overlay_compatible(
    a_meta: Mapping[str, Any],
    b_meta: Mapping[str, Any],
    *,
    metric: str = "equity",
) -> bool:
    """Whether two metric series may share one chart axis.

    Compatible only when both declare the same kind AND unit, or both declare an
    identical explicit ``normalization``. A missing/unknown kind is never
    compatible (so NAV-vs-KRW overlays are rejected rather than silently mixed).
    """

    if not (isinstance(a_meta, Mapping) and isinstance(b_meta, Mapping)):
        return False
    kind_key = f"{metric}_kind"
    unit_key = f"{metric}_unit"
    a_kind, a_unit = a_meta.get(kind_key), a_meta.get(unit_key)
    b_kind, b_unit = b_meta.get(kind_key), b_meta.get(unit_key)
    if a_kind is None or b_kind is None:
        return False
    if a_kind == b_kind and a_unit == b_unit:
        return True
    a_norm, b_norm = a_meta.get("normalization"), b_meta.get("normalization")
    return bool(a_norm) and a_norm == b_norm


def is_live_status(status: str) -> bool:
    """LIVE is exactly the RUNNING status; nothing else may render LIVE."""

    return status == RUN_STATUS_RUNNING


def derive_run_status(
    *,
    event_file_exists: bool,
    event_count: int,
    declared_running: Optional[bool],
    last_step: Optional[int] = None,
    prev_step: Optional[int] = None,
    seconds_since_last_advance: Optional[float] = None,
    poll_interval_seconds: Optional[float] = None,
    is_replay: bool = False,
) -> str:
    """Deterministic run lifecycle status; LIVE (RUNNING) is fail-closed.

    RUNNING requires ALL of: the producer declaring a running state, the
    step/file advancing, and that advance being within two poll intervals.
    Polling, row presence, or fetch time alone never yield RUNNING. A finished
    or stale run therefore can never satisfy LIVE.
    """

    if not event_file_exists:
        return RUN_STATUS_MISSING
    if is_replay:
        return RUN_STATUS_REPLAY
    if not event_count:
        return RUN_STATUS_IDLE
    advancing = (
        last_step is not None
        and prev_step is not None
        and last_step > prev_step
    )
    within_window = (
        seconds_since_last_advance is not None
        and poll_interval_seconds is not None
        and seconds_since_last_advance <= 2 * poll_interval_seconds
    )
    if declared_running is True:
        return RUN_STATUS_RUNNING if (advancing and within_window) else RUN_STATUS_STALE
    if declared_running is False:
        return RUN_STATUS_COMPLETED
    # Unknown running state: never LIVE from polling. Fresh advance => stale-safe
    # RUNNING is NOT granted; classify as STALE so LIVE is fail-closed.
    return RUN_STATUS_STALE
