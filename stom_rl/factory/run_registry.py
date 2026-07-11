"""SQLite run registry for the STOM model factory.

Honesty guardrails: this is research infrastructure only — it tracks experiment
lineage and verdicts and makes no profit claim. The registry sqlite file is a
GENERATED artifact owned by the factory (default location under
``webui/rl_runs/``); it is the only sqlite the factory is allowed to write.
Tick databases remain strictly read-only and are never touched here.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import cmp_to_key
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


_MIGRATION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("authoritative", "INTEGER NOT NULL DEFAULT 0"),
    ("completed_at", "TEXT"),
    ("source_git_sha", "TEXT"),
    ("artifact_hashes", "TEXT"),
    ("run_dir", "TEXT"),
    ("total_bytes", "INTEGER"),
)


_STATUS_RANK: dict[str, int] = {"done": 0, "running": 1, "queued": 2, "failed": 3}


def init_registry(registry_path: Path | str) -> None:
    """Create the runs table if missing and apply additive migrations. Safe to call repeatedly."""

    with _connect(registry_path) as conn:
        conn.execute(_SCHEMA)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
        for column, ddl in _MIGRATION_COLUMNS:
            if column not in existing:
                conn.execute(f"ALTER TABLE runs ADD COLUMN {column} {ddl}")


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
    source_git_sha: str | None = None,
    run_dir: str | None = None,
    artifact_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Insert a run in ``queued`` status and return its row dict."""

    if stage not in VALID_STAGES:
        raise RegistryError(f"invalid_stage:{stage}")
    init_registry(registry_path)
    now = _utc_now()
    artifact_hashes_json = json.dumps(artifact_hashes) if artifact_hashes is not None else None
    try:
        with _connect(registry_path) as conn:
            conn.execute(
                "INSERT INTO runs (run_id, split_hash, cost_bps, seed, stage, parent_run,"
                " prereg_doc, status, verdict, created_utc, updated_utc,"
                " source_git_sha, run_dir, artifact_hashes)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', '', ?, ?, ?, ?, ?)",
                (
                    run_id,
                    split_hash,
                    float(cost_bps),
                    seed,
                    stage,
                    parent_run,
                    prereg_doc,
                    now,
                    now,
                    source_git_sha,
                    run_dir,
                    artifact_hashes_json,
                ),
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
    completed_at = None
    if status == "done" and not current.get("completed_at"):
        completed_at = _utc_now()
    with _connect(registry_path) as conn:
        if verdict is None:
            if completed_at is not None:
                conn.execute(
                    "UPDATE runs SET status = ?, updated_utc = ?, completed_at = ? WHERE run_id = ?",
                    (status, _utc_now(), completed_at, run_id),
                )
            else:
                conn.execute(
                    "UPDATE runs SET status = ?, updated_utc = ? WHERE run_id = ?",
                    (status, _utc_now(), run_id),
                )
        else:
            if completed_at is not None:
                conn.execute(
                    "UPDATE runs SET status = ?, verdict = ?, updated_utc = ?, completed_at = ?"
                    " WHERE run_id = ?",
                    (status, verdict, _utc_now(), completed_at, run_id),
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def promote_run(
    registry_path: Path | str,
    run_id: str,
    *,
    artifact_dir: Path | str,
    expected_hashes: dict[str, str],
    max_total_bytes: int,
    require_status: str = "done",
) -> dict[str, Any]:
    """Validate and promote a run to authoritative for its stage.

    All validation happens before any write; on failure the registry is left
    byte-unchanged. On success, exactly one other update demotes every other
    run sharing the same ``stage`` inside the same transaction.
    """

    row = get_run(registry_path, run_id)
    if row is None:
        raise RegistryError(f"unknown_run_id:{run_id}")
    if row.get("status") != require_status:
        raise RegistryError(f"not_ready_status:{row.get('status')}")

    for field, kind in (
        ("prereg_doc", "text"),
        ("cost_bps", "numeric"),
        ("split_hash", "text"),
        ("seed", "numeric"),
        ("source_git_sha", "text"),
    ):
        value = row.get(field)
        if value is None:
            raise RegistryError(f"missing_metadata:{field}")
        if kind == "text" and isinstance(value, str) and not value.strip():
            raise RegistryError(f"missing_metadata:{field}")

    artifact_path = Path(artifact_dir)
    if not artifact_path.is_dir():
        raise RegistryError(f"artifact_dir_missing:{artifact_dir}")

    total_bytes = 0
    for relpath, expected_hex in expected_hashes.items():
        file_path = artifact_path / relpath
        if not file_path.is_file():
            raise RegistryError(f"hash_mismatch:{relpath}")
        actual_hex = _sha256_file(file_path)
        if actual_hex.lower() != str(expected_hex).lower():
            raise RegistryError(f"hash_mismatch:{relpath}")
        total_bytes += file_path.stat().st_size

    if total_bytes > int(max_total_bytes):
        raise RegistryError(f"oversize:{total_bytes}>{max_total_bytes}")

    stage = row.get("stage")
    now = _utc_now()
    artifact_hashes_json = json.dumps(expected_hashes)
    with _connect(registry_path) as conn:
        conn.execute(
            "UPDATE runs SET authoritative = 1, run_dir = ?, artifact_hashes = ?,"
            " total_bytes = ?, updated_utc = ? WHERE run_id = ?",
            (str(artifact_path), artifact_hashes_json, total_bytes, now, run_id),
        )
        conn.execute(
            "UPDATE runs SET authoritative = 0 WHERE stage = ? AND run_id != ?",
            (stage, run_id),
        )
    updated = get_run(registry_path, run_id)
    assert updated is not None
    return updated


def _authoritative_sort_key(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def _compare(a: dict[str, Any], b: dict[str, Any]) -> int:
        a_auth = int(a.get("authoritative") or 0)
        b_auth = int(b.get("authoritative") or 0)
        if a_auth != b_auth:
            return -1 if a_auth > b_auth else 1
        a_rank = _STATUS_RANK.get(a.get("status"), 99)
        b_rank = _STATUS_RANK.get(b.get("status"), 99)
        if a_rank != b_rank:
            return -1 if a_rank < b_rank else 1
        a_completed = a.get("completed_at")
        b_completed = b.get("completed_at")
        if a_completed != b_completed:
            if a_completed is None:
                return 1
            if b_completed is None:
                return -1
            return -1 if a_completed > b_completed else 1
        a_updated = a.get("updated_utc") or ""
        b_updated = b.get("updated_utc") or ""
        if a_updated != b_updated:
            return -1 if a_updated > b_updated else 1
        return 0

    return sorted(rows, key=cmp_to_key(_compare))


def select_authoritative(
    registry_path: Path | str,
    *,
    stage: str | None = None,
) -> list[dict[str, Any]]:
    """Return runs ordered by authoritative selection precedence.

    Order: authoritative DESC, status rank (done > running > queued > failed),
    completed_at DESC with NULLs last, then updated_utc DESC as the final
    tie-break.
    """

    init_registry(registry_path)
    query = "SELECT * FROM runs"
    params: list[Any] = []
    if stage is not None:
        query += " WHERE stage = ?"
        params.append(stage)
    with _connect(registry_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return _authoritative_sort_key([_row_to_dict(row) for row in rows])


def get_authoritative(
    registry_path: Path | str,
    *,
    stage: str | None = None,
) -> dict[str, Any] | None:
    """Return the top-ranked authoritative run for ``stage``, or None."""

    rows = select_authoritative(registry_path, stage=stage)
    return rows[0] if rows else None
