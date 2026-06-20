"""Preregistration-enforcing experiment queue over the factory run registry.

Honesty guardrails: research-only orchestration, no profit claim. Every
experiment must reference an existing preregistration document before it can
enter the queue, the round-trip cost assumption is pinned at 23.0bp, and
full/walkforward stages require recorded parent lineage. The dashboard reads
queue snapshots; it never writes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .run_registry import get_run, list_runs, register_run, set_status, _connect, init_registry

REQUIRED_COST_BPS = 23.0
_STAGES_REQUIRING_PARENT = ("full", "walkforward")

READ_ONLY_DASHBOARD_NOTE = (
    "Dashboard consumption is read-only: no training, no orders, no registry writes "
    "from webui. Research tracking only — no profit claim."
)


class QueueGuardError(ValueError):
    """Raised when an experiment fails a preregistration/cost/lineage guard."""


def enqueue_experiment(
    registry_path: Path | str,
    *,
    run_id: str,
    split_hash: str,
    cost_bps: float,
    seed: int,
    stage: str,
    prereg_doc: str,
    parent_run: str | None = None,
    repo_root: Path | str = ".",
) -> dict[str, Any]:
    """Guard-check an experiment and register it as queued."""

    _guard_prereg_doc(prereg_doc, repo_root)
    if float(cost_bps) != REQUIRED_COST_BPS:
        raise QueueGuardError("cost_must_be_23bp")
    if get_run(registry_path, run_id) is not None:
        raise QueueGuardError("duplicate_run_id")
    if stage in _STAGES_REQUIRING_PARENT:
        if not parent_run or get_run(registry_path, parent_run) is None:
            raise QueueGuardError("missing_parent_lineage")
    return register_run(
        registry_path,
        run_id=run_id,
        split_hash=split_hash,
        cost_bps=cost_bps,
        seed=seed,
        stage=stage,
        prereg_doc=prereg_doc,
        parent_run=parent_run,
    )


def next_queued(registry_path: Path | str) -> dict[str, Any] | None:
    """Return the oldest queued run, or None when the queue is empty."""

    init_registry(registry_path)
    with _connect(registry_path) as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE status = 'queued'"
            " ORDER BY created_utc ASC, rowid ASC LIMIT 1"
        ).fetchone()
    return {key: row[key] for key in row.keys()} if row is not None else None


def mark_running(registry_path: Path | str, run_id: str) -> dict[str, Any]:
    return set_status(registry_path, run_id, "running")


def mark_done(registry_path: Path | str, run_id: str, *, verdict: str = "") -> dict[str, Any]:
    return set_status(registry_path, run_id, "done", verdict=verdict)


def mark_failed(registry_path: Path | str, run_id: str, *, verdict: str = "") -> dict[str, Any]:
    return set_status(registry_path, run_id, "failed", verdict=verdict)


def queue_snapshot(registry_path: Path | str) -> dict[str, Any]:
    """JSON-safe snapshot: status counts, latest 20 runs, guardrail note."""

    init_registry(registry_path)
    with _connect(registry_path) as conn:
        rows = conn.execute("SELECT status, COUNT(*) AS n FROM runs GROUP BY status").fetchall()
    counts = {status: 0 for status in ("queued", "running", "done", "failed")}
    for row in rows:
        counts[row["status"]] = int(row["n"])
    return {
        "registry_path": str(registry_path),
        "counts_by_status": counts,
        "latest_runs": list_runs(registry_path, limit=20),
        "read_only_dashboard_note": READ_ONLY_DASHBOARD_NOTE,
    }


def _guard_prereg_doc(prereg_doc: str, repo_root: Path | str) -> None:
    if not prereg_doc:
        raise QueueGuardError("missing_prereg_doc")
    doc_path = Path(prereg_doc)
    if doc_path.is_absolute():
        raise QueueGuardError("missing_prereg_doc")
    root = Path(repo_root).resolve()
    candidate = (root / doc_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise QueueGuardError("missing_prereg_doc") from None
    if not candidate.is_file():
        raise QueueGuardError("missing_prereg_doc")
