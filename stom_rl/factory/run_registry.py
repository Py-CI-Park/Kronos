"""SQLite run registry for the STOM model factory.

Honesty guardrails: this is research infrastructure only — it tracks experiment
lineage and verdicts and makes no profit claim. The registry sqlite file is a
GENERATED artifact owned by the factory (default location under
``webui/rl_runs/``); it is the only sqlite the factory is allowed to write.
Tick databases remain strictly read-only and are never touched here.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DEFAULT_REGISTRY_PATH = Path("webui") / "rl_runs" / "factory_registry.sqlite"

VALID_STAGES = ("smoke", "full", "walkforward", "paper")
VALID_STATUSES = ("queued", "running", "done", "failed")

_LEGAL_TRANSITIONS: dict[tuple[str, str], bool] = {
    ("queued", "running"): True,
    ("running", "done"): True,
    ("running", "failed"): True,
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    split_hash TEXT,
    cost_bps REAL NOT NULL,
    seed INTEGER,
    stage TEXT CHECK(stage IN ('smoke','full','walkforward','paper')),
    parent_run TEXT,
    prereg_doc TEXT NOT NULL,
    status TEXT CHECK(status IN ('queued','running','done','failed')) DEFAULT 'queued',
    verdict TEXT DEFAULT '',
    created_utc TEXT,
    updated_utc TEXT
)
"""


class RegistryError(ValueError):
    """Raised on illegal registry operations (bad transition, unknown run, duplicate)."""


@contextmanager
def _connect(registry_path: Path | str) -> Iterator[sqlite3.Connection]:
    path = Path(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def init_registry(registry_path: Path | str) -> None:
    """Create the runs table if missing. Safe to call repeatedly."""

    with _connect(registry_path) as conn:
        conn.execute(_SCHEMA)


def register_run(
    registry_path: Path | str,
    *,
    run_id: str,
    split_hash: str,
    cost_bps: float,
    seed: int,
    stage: str,
    prereg_doc: str,
    parent_run: str | None = None,
) -> dict[str, Any]:
    """Insert a run in ``queued`` status and return its row dict."""

    if stage not in VALID_STAGES:
        raise RegistryError(f"invalid_stage:{stage}")
    init_registry(registry_path)
    now = _utc_now()
    try:
        with _connect(registry_path) as conn:
            conn.execute(
                "INSERT INTO runs (run_id, split_hash, cost_bps, seed, stage, parent_run,"
                " prereg_doc, status, verdict, created_utc, updated_utc)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', '', ?, ?)",
                (run_id, split_hash, float(cost_bps), seed, stage, parent_run, prereg_doc, now, now),
            )
    except sqlite3.IntegrityError as exc:
        raise RegistryError(f"duplicate_run_id:{run_id}") from exc
    row = get_run(registry_path, run_id)
    assert row is not None
    return row


def set_status(
    registry_path: Path | str,
    run_id: str,
    status: str,
    *,
    verdict: str | None = None,
) -> dict[str, Any]:
    """Apply a legal status transition; illegal transitions raise RegistryError."""

    if status not in VALID_STATUSES:
        raise RegistryError(f"invalid_status:{status}")
    current = get_run(registry_path, run_id)
    if current is None:
        raise RegistryError(f"unknown_run_id:{run_id}")
    if not _LEGAL_TRANSITIONS.get((current["status"], status)):
        raise RegistryError(f"illegal_transition:{current['status']}->{status}")
    with _connect(registry_path) as conn:
        if verdict is None:
            conn.execute(
                "UPDATE runs SET status = ?, updated_utc = ? WHERE run_id = ?",
                (status, _utc_now(), run_id),
            )
        else:
            conn.execute(
                "UPDATE runs SET status = ?, verdict = ?, updated_utc = ? WHERE run_id = ?",
                (status, verdict, _utc_now(), run_id),
            )
    row = get_run(registry_path, run_id)
    assert row is not None
    return row


def get_run(registry_path: Path | str, run_id: str) -> dict[str, Any] | None:
    """Return a run row dict or None when absent."""

    init_registry(registry_path)
    with _connect(registry_path) as conn:
        cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
    return _row_to_dict(row) if row is not None else None


def list_runs(
    registry_path: Path | str,
    *,
    status: str | None = None,
    stage: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List runs newest first, optionally filtered by status and stage."""

    init_registry(registry_path)
    query = "SELECT * FROM runs"
    clauses: list[str] = []
    params: list[Any] = []
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if stage is not None:
        clauses.append("stage = ?")
        params.append(stage)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_utc DESC, rowid DESC LIMIT ?"
    params.append(int(limit))
    with _connect(registry_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def lineage(registry_path: Path | str, run_id: str) -> list[dict[str, Any]]:
    """Walk the parent_run chain to the root; root-first order, cycle-safe."""

    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    current_id: str | None = run_id
    while current_id is not None and current_id not in seen:
        seen.add(current_id)
        row = get_run(registry_path, current_id)
        if row is None:
            break
        chain.append(row)
        current_id = row.get("parent_run")
    chain.reverse()
    return chain
