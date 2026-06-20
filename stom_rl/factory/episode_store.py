"""Episode store for the STOM model-factory layer (P1).

Supplies full-universe opening episodes (per-symbol tick tables, one session
window each) from local STOM tick SQLite DBs with a transparent parquet cache.

Honesty guardrails:

- Research-only infrastructure. Nothing here is a profit claim or a live
  trading signal; downstream evaluation must stay cost-aware (23.0bp round
  trip) and OOS-gated.
- Tick DBs are opened strictly read-only (``mode=ro`` URI plus
  ``PRAGMA query_only=ON``). This module never writes to a tick DB.
- Stock symbol codes are strings with leading zeros (e.g. ``"000250"``) and
  are never coerced to int; cache round trips preserve dtypes.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd  # noqa: PANDAS_OK - existing STOM tick pipelines are pandas-based

DEFAULT_TIME_START = "090000"
DEFAULT_TIME_END = "093000"
DEFAULT_EPISODE_CACHE_DIR = Path(".omx") / "artifacts" / "factory_episode_cache"

GUARDRAIL_NOTE = (
    "research-only episode supply layer; read-only tick DB access; "
    "no profit claim; downstream evaluation must remain cost-aware (23.0bp round trip)"
)


@dataclass(frozen=True)
class EpisodeRef:
    """Reference to one per-symbol session window inside a tick DB."""

    table: str
    session: str
    time_start: str = DEFAULT_TIME_START
    time_end: str = DEFAULT_TIME_END


def connect_readonly(db_path: str | Path) -> sqlite3.Connection:
    """Open a tick DB strictly read-only (``mode=ro`` URI + ``query_only``)."""

    path = Path(db_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"SQLite DB not found: {path}")
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _list_stock_tables(conn: sqlite3.Connection, *, max_tables: int | None = None) -> list[str]:
    names = [
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        if str(row[0]).isdigit()
    ]
    if max_tables is not None and max_tables > 0:
        return names[: int(max_tables)]
    return names


def list_stock_tables(db_path: str | Path, *, max_tables: int | None = None) -> list[str]:
    """Enumerate per-symbol (all-digit) tick tables, read-only."""

    conn = connect_readonly(db_path)
    try:
        return _list_stock_tables(conn, max_tables=max_tables)
    finally:
        conn.close()


def _list_sessions(conn: sqlite3.Connection, table: str, *, max_sessions: int | None = None) -> list[str]:
    qt = _quote_ident(table)
    q = f'SELECT DISTINCT substr(CAST("index" AS TEXT), 1, 8) AS session FROM {qt} ORDER BY session'
    sessions = [str(row[0]) for row in conn.execute(q).fetchall()]
    if max_sessions is not None and max_sessions > 0:
        return sessions[: int(max_sessions)]
    return sessions


def list_sessions(db_path: str | Path, table: str, *, max_sessions: int | None = None) -> list[str]:
    """List distinct YYYYMMDD session dates for one table, read-only."""

    conn = connect_readonly(db_path)
    try:
        return _list_sessions(conn, table, max_sessions=max_sessions)
    finally:
        conn.close()


def _logical_key(ref: EpisodeRef, max_rows: int | None) -> str:
    payload = json.dumps(
        [ref.table, ref.session, ref.time_start, ref.time_end, max_rows],
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def episode_cache_key(ref: EpisodeRef, *, max_rows: int | None, columns: Iterable[Any]) -> str:
    """Cache key: sha256 of (table, session, window, max_rows, sorted columns), 16 hex chars."""

    payload = json.dumps(
        [
            ref.table,
            ref.session,
            ref.time_start,
            ref.time_end,
            max_rows,
            sorted(str(col) for col in columns),
        ],
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _find_cached(cache_dir: Path, logical: str) -> Path | None:
    matches = sorted(cache_dir.glob(f"{logical}_*.parquet"))
    return matches[0] if matches else None


def _load_episode_frame(conn: sqlite3.Connection, ref: EpisodeRef, *, max_rows: int | None) -> pd.DataFrame:
    qt = _quote_ident(ref.table)
    q = f"""
        SELECT *
        FROM {qt}
        WHERE substr(CAST("index" AS TEXT), 1, 8) = ?
          AND substr(CAST("index" AS TEXT), 9, 6) >= ?
          AND substr(CAST("index" AS TEXT), 9, 6) <= ?
        ORDER BY "index"
    """
    params: list[Any] = [str(ref.session), str(ref.time_start), str(ref.time_end)]
    if max_rows is not None and max_rows > 0:
        q += " LIMIT ?"
        params.append(int(max_rows))
    return pd.read_sql_query(q, conn, params=tuple(params))


def load_episode(
    db_path: str | Path,
    ref: EpisodeRef,
    *,
    max_rows: int | None = None,
    cache_dir: Path | str | None = None,
) -> pd.DataFrame:
    """Load one session window; transparently parquet-cache when ``cache_dir`` is set.

    On a cache hit the tick DB is never touched, so the source DB may be
    absent. The cached frame is written as-is so all column dtypes (including
    leading-zero symbol/code strings) round-trip unchanged.
    """

    cache_root = Path(cache_dir) if cache_dir is not None else None
    logical = _logical_key(ref, max_rows)
    if cache_root is not None:
        cached = _find_cached(cache_root, logical)
        if cached is not None:
            return pd.read_parquet(cached)
    conn = connect_readonly(db_path)
    try:
        frame = _load_episode_frame(conn, ref, max_rows=max_rows)
    finally:
        conn.close()
    if cache_root is not None:
        cache_root.mkdir(parents=True, exist_ok=True)
        key = episode_cache_key(ref, max_rows=max_rows, columns=frame.columns)
        frame.to_parquet(cache_root / f"{logical}_{key}.parquet", index=False)
    return frame


def sample_episode_refs(
    db_path: str | Path,
    *,
    n: int,
    seed: int,
    max_tables: int | None = None,
    max_sessions_per_table: int | None = None,
) -> list[EpisodeRef]:
    """Deterministically sample episode refs without replacement.

    Same ``seed`` yields the identical list (candidates are enumerated in
    sorted table/session order before ``numpy.random.default_rng`` sampling).
    """

    if n <= 0:
        return []
    conn = connect_readonly(db_path)
    try:
        candidates = [
            EpisodeRef(table=table, session=session)
            for table in _list_stock_tables(conn, max_tables=max_tables)
            for session in _list_sessions(conn, table, max_sessions=max_sessions_per_table)
        ]
    finally:
        conn.close()
    if not candidates:
        return []
    rng = np.random.default_rng(int(seed))
    size = min(int(n), len(candidates))
    picks = rng.choice(len(candidates), size=size, replace=False)
    return [candidates[int(i)] for i in picks]


def store_manifest(
    refs: Sequence[EpisodeRef],
    *,
    db_path: str | Path,
    cache_dir: Path | str | None,
) -> dict[str, Any]:
    """JSON-safe manifest describing a batch of episode refs."""

    refs = list(refs)
    tables = sorted({ref.table for ref in refs})
    sessions = sorted({ref.session for ref in refs})
    windows = sorted({f"{ref.time_start}-{ref.time_end}" for ref in refs})
    return {
        "artifact_type": "factory_episode_store_manifest",
        "db_path": str(db_path),
        "ref_count": len(refs),
        "tables": tables,
        "table_count": len(tables),
        "sessions": sessions,
        "session_count": len(sessions),
        "time_windows": windows,
        "cache_dir": str(cache_dir) if cache_dir is not None else None,
        "read_only": True,
        "guardrail": GUARDRAIL_NOTE,
    }
