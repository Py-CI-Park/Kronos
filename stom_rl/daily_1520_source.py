"""Read-only exact 15:20 KST source adapter for the 5-minute OHLCV DB.

This module is additive and intentionally does not reuse the legacy daily OHLCV
helpers: 15:20 is a causal proxy, not the official close, and missing bars are
reported explicitly instead of falling back to nearest or full-day daily values.
"""
from __future__ import annotations

import hashlib
import math
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date as Date
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_5MIN_DB_PATH = REPO_ROOT / "_database" / "Stock_Database_ohlcv_5min.db"

SCHEMA_VERSION = "kronos_daily_1520_source.v1"
CAUSAL_CUTOFF_KST = "15:20:00"
PRICE_BASIS = "15:20_bar_close_proxy"
OFFICIAL_CLOSE = False

EXPECTED_COLUMNS: tuple[str, ...] = ("date", "open", "high", "low", "close", "volume")
TABLE_RE = re.compile(r"^A[0-9]{6}$")
SYMBOL_RE = re.compile(r"^[0-9]{6}$")
CUTOFF_HHMM = 1520
COMPACT_1520_RE = re.compile(r"^\d{8}1520$")

BAR_VOLUME_STATUS = "SINGLE_5MIN_BAR_VOLUME_AT_15_20_ONLY"
UNAVAILABLE_CUMULATIVE_VOLUME_STATUS = "NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY"
UNAVAILABLE_AMOUNT_STATUS = "NOT_AVAILABLE_5MIN_DB_HAS_NO_AMOUNT_COLUMN_DO_NOT_APPROXIMATE_PRICE_X_VOLUME"
MISSING_1520_BAR_REASON = "MISSING_1520_BAR"
SOURCE_HASH_BASIS = "ACTUAL_FILE_BYTES_STREAMING_SHA256"
MISSING_DATE_POLICY = (
    "Expected dates are each table's own observed valid intraday source calendar within the requested range; "
    "missing dates are explicit and source rows are never synthesized."
)
FALSE_RESEARCH_LOCKS: dict[str, bool] = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}
NO_CLAIM_FLAGS: dict[str, bool] = {
    "official_close_claim": False,
    "daily_ohlcv_fallback_claim": False,
    "nearest_bar_fallback_claim": False,
    "paper_forward_claim": False,
    "live_broker_order_claim": False,
    "profitability_claim": False,
}


@dataclass(frozen=True)
class FiveMinTableRef:
    """Resolved 5-minute table identity, preserving the six-digit symbol."""

    table: str
    symbol: str
    prefix: str


@dataclass(frozen=True)
class Daily1520SourceRow:
    """One real exact-15:20 source row.

    ``bar_volume_1520`` is the single 5-minute bar volume. Cumulative volume and
    amount are deliberately unavailable because the source DB has no cumulative
    or amount columns and this adapter must not approximate amount as
    price*volume.
    """

    schema_version: str
    session_date: str
    date: str
    timestamp_kst: str
    timestamp_yyyymmddhhmm: int
    symbol: str
    table: str
    open: int | float
    high: int | float
    low: int | float
    close: int | float
    price_1520_close_proxy: int | float
    bar_volume_1520: int | float
    bar_volume_status: str
    volume_to_1520: None
    volume_to_1520_status: str
    cumulative_volume_to_1520: None
    cumulative_volume_to_1520_status: str
    amount_to_1520: None
    amount_to_1520_status: str
    tradable: bool
    exclusion_reason: str | None
    official_close: bool
    price_basis: str
    causal_cutoff_kst: str
    source_db_path: str
    source_table: str
    source_columns: tuple[str, ...]
    source_timestamp_column: str
    source_price_column: str
    source_volume_column: str

    def as_dict(self) -> dict[str, Any]:
        payload = _jsonable(asdict(self))
        payload["timestamp_yyyymmddhhmm"] = _compact_1520_timestamp_string(self.timestamp_yyyymmddhhmm)
        return payload


@dataclass(frozen=True)
class _CoverageSeed:
    requested: str
    table_ref: FiveMinTableRef
    exact_dates: tuple[str, ...]
    observed_dates: tuple[str, ...]
    duplicate_date_count: int


def connect_readonly(db_path: Path | str = DEFAULT_5MIN_DB_PATH) -> sqlite3.Connection:
    """Open the 5-minute SQLite DB in read-only and query-only mode."""

    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(path)
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def resolve_5min_table(symbol_or_table: str) -> FiveMinTableRef:
    """Resolve a six-digit KRX stock symbol or ``A######`` table.

    Only numeric ``A``-prefixed stock tables are accepted. Six-digit symbols are
    never coerced to integers, so leading zeros are preserved.
    """

    raw = str(symbol_or_table or "").strip()
    if TABLE_RE.match(raw):
        table = raw
    elif SYMBOL_RE.match(raw):
        table = f"A{raw}"
    else:
        raise ValueError("5-minute symbols must be six numeric digits or A-prefixed numeric stock tables")
    return FiveMinTableRef(table=table, symbol=table[1:], prefix=table[0])


def read_exact_1520_rows(
    db_path: Path | str,
    symbol_or_table: str,
    *,
    start_date: str | int | Date | None = None,
    end_date: str | int | Date | None = None,
) -> list[Daily1520SourceRow]:
    """Return real exact 15:20 rows only, with no nearest or daily fallback."""

    table_ref = resolve_5min_table(symbol_or_table)
    start_yyyymmdd = _coerce_session_date(start_date, "start_date")
    end_yyyymmdd = _coerce_session_date(end_date, "end_date")
    if start_yyyymmdd is not None and end_yyyymmdd is not None and start_yyyymmdd > end_yyyymmdd:
        raise ValueError("start_date must be on or before end_date")

    path = Path(db_path)
    with connect_readonly(path) as conn:
        _require_table(conn, table_ref.table)
        _require_exact_schema(conn, table_ref.table)
        return _read_rows(conn, path, table_ref, start_yyyymmdd=start_yyyymmdd, end_yyyymmdd=end_yyyymmdd)


def build_source_artifact(
    db_path: Path | str,
    symbol_or_table: str,
    *,
    start_date: str | int | Date | None = None,
    end_date: str | int | Date | None = None,
) -> dict[str, Any]:
    """Return the executable V5.1 source artifact for one 15:20 table.

    The artifact preserves the existing coverage manifest shape and adds the
    exact JSON-compatible rows emitted by :func:`read_exact_1520_rows`.
    """

    rows = read_exact_1520_rows(db_path, symbol_or_table, start_date=start_date, end_date=end_date)
    artifact = build_source_coverage(db_path, [symbol_or_table], start_date=start_date, end_date=end_date)
    artifact["rows"] = [_jsonable(row.as_dict()) for row in rows]
    return artifact


def build_source_coverage(
    db_path: Path | str,
    symbols_or_tables: Iterable[str],
    *,
    start_date: str | int | Date | None = None,
    end_date: str | int | Date | None = None,
) -> dict[str, Any]:
    """Build exact-15:20 coverage and source byte identity for requested tables."""

    requested = [str(value) for value in symbols_or_tables]
    if not requested:
        raise ValueError("symbols_or_tables must contain at least one symbol or table")

    start_yyyymmdd = _coerce_session_date(start_date, "start_date")
    end_yyyymmdd = _coerce_session_date(end_date, "end_date")
    if start_yyyymmdd is not None and end_yyyymmdd is not None and start_yyyymmdd > end_yyyymmdd:
        raise ValueError("start_date must be on or before end_date")

    path = Path(db_path)
    snapshot = _source_snapshot(path)
    with connect_readonly(path) as conn:
        query_only = bool(conn.execute("PRAGMA query_only").fetchone()[0])
        seeds: list[_CoverageSeed] = []
        for value in requested:
            table_ref = resolve_5min_table(value)
            _require_table(conn, table_ref.table)
            _require_exact_schema(conn, table_ref.table)
            exact_dates = tuple(
                _valid_1520_session_dates(
                    conn,
                    table_ref.table,
                    start_yyyymmdd=start_yyyymmdd,
                    end_yyyymmdd=end_yyyymmdd,
                )
            )
            observed_dates = tuple(
                _valid_intraday_session_dates(
                    conn,
                    table_ref.table,
                    start_yyyymmdd=start_yyyymmdd,
                    end_yyyymmdd=end_yyyymmdd,
                )
            )
            duplicate_count = len(exact_dates) - len(set(exact_dates))
            seeds.append(
                _CoverageSeed(
                    requested=value,
                    table_ref=table_ref,
                    exact_dates=exact_dates,
                    observed_dates=observed_dates,
                    duplicate_date_count=duplicate_count,
                )
            )

    source_calendar = tuple(sorted({date for seed in seeds for date in seed.observed_dates}))
    tables: list[dict[str, Any]] = []
    total_exact = 0
    total_missing = 0
    for seed in seeds:
        exact_date_set = set(seed.exact_dates)
        observed_calendar = tuple(sorted(set(seed.observed_dates)))
        first_valid = observed_calendar[0] if observed_calendar else None
        last_valid = observed_calendar[-1] if observed_calendar else None
        expected_dates = list(observed_calendar)
        missing_dates = [date for date in expected_dates if date not in exact_date_set]
        total_exact += len(seed.exact_dates)
        total_missing += len(missing_dates)
        tables.append(
            {
                "requested": seed.requested,
                "symbol": seed.table_ref.symbol,
                "table": seed.table_ref.table,
                "source_columns": list(EXPECTED_COLUMNS),
                "first_valid_date": first_valid,
                "last_valid_date": last_valid,
                "exact_1520_row_count": len(seed.exact_dates),
                "valid_session_count": len(observed_calendar),
                "duplicate_1520_date_count": seed.duplicate_date_count,
                "expected_session_count": len(expected_dates),
                "missing_1520_date_count": len(missing_dates),
                "missing_dates": missing_dates,
                "missing_exclusion_reason": MISSING_1520_BAR_REASON,
                "missing_rows_synthesized": False,
                "tradable_when_missing": False,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "source_db_path": str(path.resolve()),
        "source_snapshot": snapshot,
        "source_db_sha256": snapshot["sha256"],
        "source_hash_basis": SOURCE_HASH_BASIS,
        "read_only": True,
        "query_only": query_only,
        "causal_cutoff_kst": CAUSAL_CUTOFF_KST,
        "price_basis": PRICE_BASIS,
        "official_close": OFFICIAL_CLOSE,
        "source_calendar": list(source_calendar),
        "first_valid_date": source_calendar[0] if source_calendar else None,
        "last_valid_date": source_calendar[-1] if source_calendar else None,
        "exact_1520_row_count": total_exact,
        "missing_1520_date_count": total_missing,
        "missing_date_policy": MISSING_DATE_POLICY,
        "missing_rows_synthesized": False,
        "false_research_locks": dict(FALSE_RESEARCH_LOCKS),
        "six_locks_false": dict(FALSE_RESEARCH_LOCKS),
        "no_claim_flags": dict(NO_CLAIM_FLAGS),
        "tables": tables,
    }


def _quote_ident(name: str) -> str:
    if not TABLE_RE.match(name):
        raise ValueError(f"Invalid 5-minute table name: {name!r}")
    return '"' + name.replace('"', '""') + '"'


def _require_table(conn: sqlite3.Connection, table: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? AND name NOT LIKE 'sqlite_%'",
        (table,),
    ).fetchone()
    if row is None:
        raise ValueError(f"5-minute table does not exist: {table}")


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({_quote_ident(table)})").fetchall()
    return [str(row[1]) for row in rows]


def _require_exact_schema(conn: sqlite3.Connection, table: str) -> None:
    columns = tuple(_table_columns(conn, table))
    if columns != EXPECTED_COLUMNS:
        raise ValueError(f"5-minute table {table} schema must be exactly {list(EXPECTED_COLUMNS)}, got {list(columns)}")


def _read_rows(
    conn: sqlite3.Connection,
    db_path: Path,
    table_ref: FiveMinTableRef,
    *,
    start_yyyymmdd: int | None,
    end_yyyymmdd: int | None,
) -> list[Daily1520SourceRow]:
    qt = _quote_ident(table_ref.table)
    clauses = ["CAST(date AS INTEGER) % 10000 = ?"]
    params: list[Any] = [CUTOFF_HHMM]
    if start_yyyymmdd is not None:
        clauses.append("CAST(date AS INTEGER) >= ?")
        params.append(start_yyyymmdd * 10000)
    if end_yyyymmdd is not None:
        clauses.append("CAST(date AS INTEGER) <= ?")
        params.append(end_yyyymmdd * 10000 + 2359)
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"SELECT date, open, high, low, close, volume FROM {qt} WHERE {where} ORDER BY CAST(date AS INTEGER), rowid",
        params,
    ).fetchall()
    return [_row_from_sqlite(db_path, table_ref, row) for row in rows]


def _row_from_sqlite(db_path: Path, table_ref: FiveMinTableRef, row: sqlite3.Row) -> Daily1520SourceRow:
    timestamp = _validate_1520_timestamp(row["date"])
    session_date = _session_date(timestamp)
    open_price = _coerce_number(row["open"], "open")
    high_price = _coerce_number(row["high"], "high")
    low_price = _coerce_number(row["low"], "low")
    close_price = _coerce_number(row["close"], "close")
    bar_volume = _coerce_number(row["volume"], "volume")
    return Daily1520SourceRow(
        schema_version=SCHEMA_VERSION,
        session_date=session_date,
        date=session_date,
        timestamp_kst=f"{session_date}T15:20:00+09:00",
        timestamp_yyyymmddhhmm=timestamp,
        symbol=table_ref.symbol,
        table=table_ref.table,
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        price_1520_close_proxy=close_price,
        bar_volume_1520=bar_volume,
        bar_volume_status=BAR_VOLUME_STATUS,
        volume_to_1520=None,
        volume_to_1520_status=UNAVAILABLE_CUMULATIVE_VOLUME_STATUS,
        cumulative_volume_to_1520=None,
        cumulative_volume_to_1520_status=UNAVAILABLE_CUMULATIVE_VOLUME_STATUS,
        amount_to_1520=None,
        amount_to_1520_status=UNAVAILABLE_AMOUNT_STATUS,
        tradable=True,
        exclusion_reason=None,
        official_close=OFFICIAL_CLOSE,
        price_basis=PRICE_BASIS,
        causal_cutoff_kst=CAUSAL_CUTOFF_KST,
        source_db_path=str(db_path.resolve()),
        source_table=table_ref.table,
        source_columns=EXPECTED_COLUMNS,
        source_timestamp_column="date",
        source_price_column="close",
        source_volume_column="volume",
    )


def _valid_1520_session_dates(
    conn: sqlite3.Connection,
    table: str,
    *,
    start_yyyymmdd: int | None = None,
    end_yyyymmdd: int | None = None,
) -> list[str]:
    qt = _quote_ident(table)
    clauses = ["CAST(date AS INTEGER) % 10000 = ?"]
    params: list[Any] = [CUTOFF_HHMM]
    if start_yyyymmdd is not None:
        clauses.append("CAST(date AS INTEGER) >= ?")
        params.append(start_yyyymmdd * 10000)
    if end_yyyymmdd is not None:
        clauses.append("CAST(date AS INTEGER) <= ?")
        params.append(end_yyyymmdd * 10000 + 2359)
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"SELECT date FROM {qt} WHERE {where} ORDER BY CAST(date AS INTEGER), rowid",
        params,
    ).fetchall()
    return [_session_date(_validate_1520_timestamp(row["date"])) for row in rows]


def _valid_intraday_session_dates(
    conn: sqlite3.Connection,
    table: str,
    *,
    start_yyyymmdd: int | None = None,
    end_yyyymmdd: int | None = None,
) -> list[str]:
    qt = _quote_ident(table)
    clauses: list[str] = []
    params: list[Any] = []
    if start_yyyymmdd is not None:
        clauses.append("CAST(date AS INTEGER) >= ?")
        params.append(start_yyyymmdd * 10000)
    if end_yyyymmdd is not None:
        clauses.append("CAST(date AS INTEGER) <= ?")
        params.append(end_yyyymmdd * 10000 + 2359)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT date FROM {qt}{where} ORDER BY CAST(date AS INTEGER), rowid",
        params,
    ).fetchall()
    return [_session_date(_validate_intraday_timestamp(row["date"])) for row in rows]


def _validate_1520_timestamp(value: Any) -> int:
    timestamp = _validate_intraday_timestamp(value)
    if timestamp % 10000 != CUTOFF_HHMM:
        raise ValueError(f"Timestamp must be exactly 15:20 KST, got {value!r}")
    return timestamp


def _validate_intraday_timestamp(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"5-minute date must be an integer YYYYMMDDHHMM value, got {value!r}")
    text = str(value)
    if len(text) != 12 or not text.isdigit():
        raise ValueError(f"5-minute date must be an integer YYYYMMDDHHMM value, got {value!r}")
    try:
        datetime.strptime(text, "%Y%m%d%H%M")
    except ValueError as exc:
        raise ValueError(f"Invalid YYYYMMDDHHMM timestamp: {value!r}") from exc
    return value


def _session_date(timestamp: int) -> str:
    text = str(timestamp)
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}"


def _compact_1520_timestamp_string(value: Any) -> str:
    timestamp = _validate_1520_timestamp(value)
    text = str(timestamp)
    if COMPACT_1520_RE.fullmatch(text) is None:
        raise ValueError(f"Timestamp must be compact YYYYMMDD1520, got {value!r}")
    return text


def _coerce_session_date(value: str | int | Date | None, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, Date) and not isinstance(value, datetime):
        return int(value.strftime("%Y%m%d"))
    if isinstance(value, bool):
        raise ValueError(f"{name} must be YYYY-MM-DD or YYYYMMDD")
    raw = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        raw = raw.replace("-", "")
    if not re.fullmatch(r"\d{8}", raw):
        raise ValueError(f"{name} must be YYYY-MM-DD or YYYYMMDD")
    try:
        parsed = datetime.strptime(raw, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid calendar date") from exc
    return int(parsed.strftime("%Y%m%d"))


def _coerce_number(value: Any, name: str) -> int | float:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{name} must be a finite numeric value")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be a finite numeric value")
        return value
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite numeric value") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite numeric value")
    return number


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(value[key]) for key in sorted(value, key=lambda item: str(item))}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return [_jsonable(item) for item in sorted(value, key=lambda item: str(item))]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Date):
        return value.isoformat()
    return value


def _source_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    sha = hashlib.sha256()
    byte_length = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            byte_length += len(chunk)
            sha.update(chunk)
    return {
        "sha256": sha.hexdigest(),
        "byte_length": byte_length,
        "hash_basis": SOURCE_HASH_BASIS,
    }
