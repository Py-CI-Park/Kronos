"""Bounded public-data materializer for frozen Type 1 G002.

This module has no fresh-OOS inputs.  Every source SQL query is bounded at the
public cutoff before it executes; no combined dataset is opened or produced.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Context, Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping, Sequence

from stom_rl import daily_1520_source
from stom_rl.daily_type1_contract import FEATURES, canonical_json_bytes
from stom_rl.daily_type1_market import (
    REUSED_VALIDATION_END,
    REUSED_VALIDATION_START,
    TRAIN_END,
    TRAIN_START,
    public_row_from_mapping,
)
from stom_rl.daily_v6_dataset import (
    DEFAULT_DAILY_DB_PATH,
    DEFAULT_UNIVERSE_MANIFEST_PATH,
    load_default_universe,
)

DATASET_ID = "type1-close-20260803-001"
PUBLIC_CUTOFF = 20250630
PUBLIC_START = 20180102
PROXY_HHMM = 1520
SCHEMA_VERSION = "kronos_type1_g002_public_data.v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "docs" / "kronos_type1_g002_public_protocol_2026-07-23.json"
PREREG_PATH = REPO_ROOT / "docs" / "kronos_type1_closing_prereg_2026-07-23.json"
_DECIMAL_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)
_DAILY_COLUMNS = ("date", "close", "volume", "상장주식수", "외국인현보유비율", "기관순매수")
_FIVE_MIN_COLUMNS = ("date", "open", "high", "low", "close", "volume")


def materialize_public_data(
    *,
    daily_db_path: Path | str = DEFAULT_DAILY_DB_PATH,
    fivemin_db_path: Path | str = daily_1520_source.DEFAULT_5MIN_DB_PATH,
    universe: Sequence[str] | None = None,
    universe_manifest_path: Path | str = DEFAULT_UNIVERSE_MANIFEST_PATH,
    expected_symbol_count: int = 500,
    test_only: bool = False,
) -> dict[str, Any]:
    """Build canonical public rows entirely from cutoff-bounded read-only SQL.

    A non-500 universe is permitted only when ``test_only`` is explicitly true,
    so production materialization cannot silently shrink the frozen universe.
    """
    tables, manifest_path = _resolve_universe(universe, universe_manifest_path)
    if type(expected_symbol_count) is not int or expected_symbol_count <= 0:
        raise ValueError("expected_symbol_count must be a positive integer")
    if expected_symbol_count != 500 and not test_only:
        raise ValueError("non-500 expected_symbol_count is allowed only in test_only mode")
    if len(tables) != expected_symbol_count:
        raise ValueError(f"frozen universe requires exactly {expected_symbol_count} symbols")
    if len(set(tables)) != len(tables):
        raise ValueError("universe must not contain duplicate tables")

    daily_path, five_path = Path(daily_db_path), Path(fivemin_db_path)
    per_split_rows: dict[str, list[dict[str, Any]]] = {"train": [], "reused_validation": []}
    missing_labels: dict[str, int] = {"train": 0, "reused_validation": 0}
    missing_by_symbol: dict[str, dict[str, int]] = {}
    with _connect_readonly(daily_path) as daily_conn, _connect_readonly(five_path) as five_conn:
        for table in sorted(tables):
            ref = daily_1520_source.resolve_5min_table(table)
            _require_columns(daily_conn, ref.table, _DAILY_COLUMNS, "daily")
            _require_columns(five_conn, ref.table, _FIVE_MIN_COLUMNS, "5-minute")
            daily_rows = _read_daily_rows(daily_conn, ref.table)
            fills = _read_exact_1520_rows(five_conn, ref.table)
            rows, misses = _build_symbol_rows(ref.symbol, daily_rows, fills)
            missing_by_symbol[ref.symbol] = misses
            for split, count in misses.items():
                missing_labels[split] += count
            for row in rows:
                per_split_rows[row["split"]].append(row)

    rows = sorted((row for split_rows in per_split_rows.values() for row in split_rows), key=lambda row: (row["decision_date"], row["symbol"]))
    for row in rows:
        public_row_from_mapping({key: value for key, value in _public_schema(row).items() if key != "split"})
    serialized_rows = [_public_schema(row) for row in rows]
    row_bytes = canonical_json_bytes(serialized_rows)
    split_counts = {split: len(split_rows) for split, split_rows in per_split_rows.items()}
    split_symbols = {split: len({row["symbol"] for row in split_rows}) for split, split_rows in per_split_rows.items()}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": DATASET_ID,
        "read_only": True,
        "public_cutoff": "2025-06-30",
        "sql_predicates": {
            "daily": "CAST(date AS INTEGER) <= 20250630",
            "exact_1520": "CAST(date AS INTEGER) >= 201801021520 AND CAST(date AS INTEGER) <= 202506302359 AND CAST(date AS INTEGER) % 10000 = 1520",
        },
        "source_databases": {"daily": _file_receipt(daily_path), "fivemin": _file_receipt(five_path)},
        "universe": {
            "table_count": len(tables), "symbol_count": len({daily_1520_source.resolve_5min_table(item).symbol for item in tables}),
            "manifest_sha256": _sha256_file(manifest_path) if manifest_path is not None else None,
            "symbols": sorted(daily_1520_source.resolve_5min_table(item).symbol for item in tables),
        },
        "row_count": len(serialized_rows),
        "split_row_counts": split_counts,
        "split_symbol_counts": split_symbols,
        "missing_h1_label_counts": missing_labels,
        "missing_h1_by_symbol": missing_by_symbol,
        "odd_tails": _odd_tails(per_split_rows),
        "output_sha256": hashlib.sha256(row_bytes).hexdigest(),
        "protocol_sha256": _sha256_file(PROTOCOL_PATH),
        "prereg_sha256": _sha256_file(PREREG_PATH),
        "fresh_oos": {"state": "NOT_RUN", "read_performed": False},
    }
    return {"rows": serialized_rows, "manifest": manifest, "rows_bytes": row_bytes}


def write_public_materialization(*, out_root: Path | str, **kwargs: Any) -> dict[str, Any]:
    """Materialize the fixed identity once, using exclusive directory/file creation."""
    result = materialize_public_data(**kwargs)
    root = Path(out_root)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / DATASET_ID
    destination.mkdir()  # exclusive: an existing identity must never be overwritten
    rows_path = destination / "public_rows.json"
    manifest_path = destination / "dataset_manifest.json"
    with rows_path.open("xb") as handle:
        handle.write(result["rows_bytes"])
    with manifest_path.open("xb") as handle:
        handle.write(canonical_json_bytes(result["manifest"]))
    return {**result, "destination": destination, "rows_path": rows_path, "manifest_path": manifest_path}


def _resolve_universe(universe: Sequence[str] | None, manifest_path: Path | str) -> tuple[list[str], Path | None]:
    if universe is None:
        path = Path(manifest_path)
        return [str(item) for item in load_default_universe(path)], path
    return [str(item) for item in universe], None


def _connect_readonly(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def _quote(table: str) -> str:
    return '"' + table + '"'


def _require_columns(conn: sqlite3.Connection, table: str, expected: tuple[str, ...], label: str) -> None:
    columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({_quote(table)})")}
    missing = [column for column in expected if column not in columns]
    if missing:
        raise ValueError(f"{label} table {table} lacks required columns {missing}")


def _read_daily_rows(conn: sqlite3.Connection, table: str) -> list[dict[str, Decimal | None | int]]:
    # The cutoff is deliberately in SQL, not only in post-query validation.
    source = conn.execute(
        f'SELECT date, close, volume, "상장주식수", "외국인현보유비율", "기관순매수" FROM {_quote(table)} '
        "WHERE CAST(date AS INTEGER) <= ? ORDER BY CAST(date AS INTEGER), rowid", (PUBLIC_CUTOFF,)
    ).fetchall()
    rows = [{"date": _date_value(item[0]), "close": _decimal_or_none(item[1]), "volume": _decimal_or_none(item[2]),
             "shares": _decimal_or_none(item[3]), "foreign": _decimal_or_none(item[4]), "inst": _decimal_or_none(item[5])} for item in source]
    if len({row["date"] for row in rows}) != len(rows):
        raise ValueError(f"daily table {table} has duplicate dates")
    return rows


def _read_exact_1520_rows(conn: sqlite3.Connection, table: str) -> list[tuple[int, Decimal]]:
    source = conn.execute(
        f"SELECT date, close FROM {_quote(table)} WHERE CAST(date AS INTEGER) >= ? "
        "AND CAST(date AS INTEGER) <= ? AND CAST(date AS INTEGER) % 10000 = ? "
        "ORDER BY CAST(date AS INTEGER), rowid", (PUBLIC_START * 10000, PUBLIC_CUTOFF * 10000 + 2359, PROXY_HHMM),
    ).fetchall()
    fills: list[tuple[int, Decimal]] = []
    for item in source:
        timestamp = item[0]
        if not isinstance(timestamp, int) or timestamp % 10000 != PROXY_HHMM:
            raise ValueError("exact 15:20 source timestamp is malformed")
        fills.append((timestamp // 10000, _decimal_required(item[1], "15:20 close")))
    if len({session for session, _ in fills}) != len(fills):
        raise ValueError(f"5-minute table {table} has duplicate exact-15:20 sessions")
    return fills


def _build_symbol_rows(symbol: str, daily: Sequence[Mapping[str, Any]], fills: Sequence[tuple[int, Decimal]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    output: list[dict[str, Any]] = []
    missing = {"train": 0, "reused_validation": 0}
    pointer = 0
    dates = [int(row["date"].strftime("%Y%m%d")) for row in daily]
    for index, (session, entry) in enumerate(fills):
        split = _split_for(session)
        if split is None:
            continue
        while pointer < len(dates) and dates[pointer] < session:
            pointer += 1
        features = _features(daily[max(0, pointer - 25):pointer])
        gross_return: Decimal | None = None
        next_fill = fills[index + 1] if index + 1 < len(fills) else None
        if next_fill is not None and _split_for(next_fill[0]) == split and entry != 0:
            gross_return = next_fill[1] / entry - Decimal(1)
        else:
            missing[split] += 1
        output.append({"decision_date": _iso_date(session), "symbol": symbol, "split": split, "features": features,
                       "gross_return": gross_return, "entry_available": True})
    return output, missing


def _features(rows: Sequence[Mapping[str, Any]]) -> dict[str, Decimal | None]:
    closes = [row["close"] for row in rows]
    volumes = [row["volume"] for row in rows]
    foreign = [row["foreign"] for row in rows]
    inst = [row["inst"] for row in rows]
    shares = [row["shares"] for row in rows]
    return {"ret_1d_prev": _return(closes, 1), "ret_5d_prev": _return(closes, 5), "ret_20d_prev": _return(closes, 20),
            "vol_z_20": _zscore(volumes), "foreign_ratio_prev": foreign[-1] if foreign else None,
            "foreign_ratio_delta_5": _delta(foreign, 5), "inst_netbuy_norm_5": _normalized_sum(inst, shares[-1] if shares else None)}


def _return(values: Sequence[Decimal | None], periods: int) -> Decimal | None:
    return None if len(values) <= periods or values[-1] is None or values[-1 - periods] in (None, Decimal(0)) else values[-1] / values[-1 - periods] - Decimal(1)


def _delta(values: Sequence[Decimal | None], periods: int) -> Decimal | None:
    return None if len(values) <= periods or values[-1] is None or values[-1 - periods] is None else values[-1] - values[-1 - periods]


def _zscore(values: Sequence[Decimal | None]) -> Decimal | None:
    window = values[-20:]
    if len(window) != 20 or any(value is None for value in window):
        return None
    numbers = [value for value in window if value is not None]
    with localcontext(_DECIMAL_CONTEXT):
        mean = sum(numbers, Decimal(0)) / Decimal(20)
        variance = sum((value - mean) ** 2 for value in numbers) / Decimal(20)
        return None if variance == 0 else (numbers[-1] - mean) / variance.sqrt()


def _normalized_sum(values: Sequence[Decimal | None], denominator: Decimal | None) -> Decimal | None:
    window = values[-5:]
    return None if len(window) != 5 or denominator in (None, Decimal(0)) or any(value is None for value in window) else sum((value for value in window if value is not None), Decimal(0)) / denominator


def _split_for(session: int) -> str | None:
    current = _date_value(session)
    if TRAIN_START <= current <= TRAIN_END:
        return "train"
    if REUSED_VALIDATION_START <= current <= REUSED_VALIDATION_END:
        return "reused_validation"
    return None


def _public_schema(row: Mapping[str, Any]) -> dict[str, Any]:
    return {"decision_date": row["decision_date"], "symbol": row["symbol"], "split": row["split"],
            "features": {name: _decimal_text(row["features"][name]) for name in FEATURES},
            "gross_return": _decimal_text(row["gross_return"]), "entry_available": row["entry_available"]}


def _odd_tails(rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    for split, values in rows.items():
        ordered = sorted(values, key=lambda item: (item["decision_date"], item["symbol"]))
        result[split] = ([] if len(ordered) % 2 == 0 else [{"decision_date": ordered[-1]["decision_date"], "symbol": ordered[-1]["symbol"]}])
    return result


def _date_value(value: Any) -> date:
    raw = str(value).replace("-", "")
    if len(raw) != 8 or not raw.isdigit():
        raise ValueError("daily date must be YYYYMMDD")
    return date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))


def _iso_date(value: int) -> str:
    parsed = _date_value(value)
    return parsed.isoformat()


def _decimal_or_none(value: Any) -> Decimal | None:
    return None if value is None else _decimal_required(value, "numeric value")


def _decimal_required(value: Any, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be finite")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_receipt(path: Path) -> dict[str, Any]:
    info = path.stat()
    return {"sha256": _sha256_file(path), "size_bytes": info.st_size, "mtime_ns": info.st_mtime_ns}


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize the frozen Type 1 G002 public data only.")
    parser.add_argument("--daily-db", required=True)
    parser.add_argument("--fivemin-db", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--universe-manifest", default=str(DEFAULT_UNIVERSE_MANIFEST_PATH))
    args = parser.parse_args()
    result = write_public_materialization(out_root=args.out_root, daily_db_path=args.daily_db, fivemin_db_path=args.fivemin_db,
                                          universe_manifest_path=args.universe_manifest)
    print(json.dumps({"dataset_id": DATASET_ID, "rows_path": str(result["rows_path"]), "output_sha256": result["manifest"]["output_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
