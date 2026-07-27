"""Fail-closed lifecycle and artifact state for dashboard run records."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path
import time
from typing import ClassVar, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from stom_rl import rl_events as _ev

if __package__:
    from . import artifact_cache as _cache
    from . import rl_dashboard_files as _files
    from .rl_dashboard_files import _is_run_file, _read_run_json, _utc_mtime
else:  # pragma: no cover - script-style imports
    from webui import artifact_cache as _cache
    from webui import rl_dashboard_files as _files
    from webui.rl_dashboard_files import _is_run_file, _read_run_json, _utc_mtime

DEFAULT_POLL_INTERVAL_SECONDS = 2.0


class _TerminalBoundary(BaseModel):
    """Strict safety and identity claims shared by terminal summary and receipt."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    experiment_id: str = Field(min_length=1)
    profile: Literal["SMOKE", "PRIMARY"]
    status: Literal["SMOKE_COMPLETE", "PRIMARY_COMPLETE"]
    verdict: Literal[
        "SMOKE_INCOMPLETE",
        "PPO_ONLY_OVERFIT_CONFIRMED",
        "PPO_ONLY_OVERFIT_NOT_CONFIRMED",
    ]
    promotion_allowed: Literal[False]
    profitability_claim_allowed: Literal[False]
    prereg_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    fixture_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    def has_valid_profile_pair(self) -> bool:
        if self.profile == "SMOKE":
            return self.status == "SMOKE_COMPLETE" and self.verdict == "SMOKE_INCOMPLETE"
        return self.status == "PRIMARY_COMPLETE" and self.verdict.startswith("PPO_ONLY_OVERFIT_")


def require_discovery_terminal_receipt(
    run_dir: Path,
    summary: dict[str, object],
) -> dict[str, object]:
    """Downgrade terminal discovery claims until every receipt field agrees."""

    if summary.get("research_lane") != "rl_discovery" or summary.get("status") not in {
        "SMOKE_COMPLETE",
        "PRIMARY_COMPLETE",
    }:
        return summary
    receipt_path = run_dir / "terminal_receipt.json"
    if not _is_run_file(run_dir, receipt_path):
        return {**summary, "status": "RUNNING", "verdict": "RUNNING_NOT_EVALUATED"}
    try:
        summary_boundary = _TerminalBoundary.model_validate(summary)
        receipt_boundary = _TerminalBoundary.model_validate(_read_run_json(run_dir, receipt_path))
    except (OSError, TypeError, ValueError, ValidationError):
        return {**summary, "status": "RUNNING", "verdict": "RUNNING_NOT_EVALUATED"}
    if (
        not summary_boundary.has_valid_profile_pair()
        or not receipt_boundary.has_valid_profile_pair()
        or summary_boundary != receipt_boundary
    ):
        return {**summary, "status": "RUNNING", "verdict": "RUNNING_NOT_EVALUATED"}
    return summary


def artifact_files(run_dir: Path) -> list[dict[str, object]]:
    """List contained run files without opening large artifact bodies."""

    files: list[dict[str, object]] = []
    for path in sorted(run_dir.rglob("*")):
        if _is_run_file(run_dir, path):
            files.append(
                {
                    "name": path.relative_to(run_dir).as_posix(),
                    "suffix": path.suffix.lower(),
                    "size_bytes": path.stat().st_size,
                    "modified_at": _utc_mtime(path),
                }
            )
    return files


def baseline_policies(run_dir: Path) -> list[str]:
    """Return contained baseline policy directories with known evidence files."""

    policies: list[str] = []
    for child in sorted(run_dir.iterdir()):
        if child.is_dir() and any(
            (child / file_name).is_file()
            for file_name in ("actions.csv", "trades.csv", "equity.csv", "episodes.csv")
        ):
            policies.append(child.name)
    return policies


def _find_event_file(run_dir: Path) -> Path | None:
    for name in _files.LIVE_EVENT_FILE_NAMES:
        candidate = run_dir / name
        if _is_run_file(run_dir, candidate):
            return candidate
    return None


def run_lifecycle(run_dir: Path) -> dict[str, object]:
    """Return a truthful snapshot status that never invents a live producer."""

    event_path = _find_event_file(run_dir)
    if event_path is None:
        return {
            "status": _ev.RUN_STATUS_MISSING,
            "is_live": False,
            "event_file": None,
            "event_count": 0,
            "last_step": None,
            "event_mtime_age_sec": None,
            "last_phase": None,
            "is_replay": False,
            "poll_interval_seconds": DEFAULT_POLL_INTERVAL_SECONDS,
        }
    rows = cast(
        list[dict[str, object]],
        _cache.cached_read_live_events(event_path, limit=_ev.MAX_EVENT_LIMIT, tail=True)[0],
    )
    last = rows[-1] if rows else {}
    raw_step = last.get("global_step")
    try:
        last_step = int(raw_step) if isinstance(raw_step, (int, float, str)) else None
    except (TypeError, ValueError):
        last_step = None
    age = max(0.0, time.time() - event_path.stat().st_mtime)
    last_phase = str(last.get("phase") or "")
    last_source = str(last.get("source") or "")
    is_replay = last_phase == "backtest" or "backtest" in last_source
    status = _ev.derive_run_status(
        event_file_exists=True,
        event_count=len(rows),
        declared_running=False,
        last_step=last_step,
        prev_step=None,
        seconds_since_last_advance=age,
        poll_interval_seconds=DEFAULT_POLL_INTERVAL_SECONDS,
        is_replay=is_replay,
    )
    return {
        "status": status,
        "is_live": _ev.is_live_status(status),
        "event_file": event_path.name,
        "event_count": len(rows),
        "last_step": last_step,
        "event_mtime_age_sec": round(age, 3),
        "last_phase": last_phase or None,
        "is_replay": is_replay,
        "poll_interval_seconds": DEFAULT_POLL_INTERVAL_SECONDS,
    }
