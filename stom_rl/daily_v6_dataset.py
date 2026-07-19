"""Research-only causal daily-feature / exact-15:20 label dataset builder."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import quote

from stom_rl import daily_1520_source

SCHEMA_VERSION = "kronos_v6_joined_dataset.v1"
FEATURE_TIMING = "daily_db_rows_strictly_before_fill_session_only"
DAILY_PRICE_BASIS_CAVEAT = (
    "daily DB price basis UNKNOWN_CONFIRMED; usable as feature inputs only, never as return evidence"
)
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DAILY_DB_PATH = REPO_ROOT / "_database" / "Stock_Database_ohlcv_1day.db"
DEFAULT_UNIVERSE_MANIFEST_PATH = REPO_ROOT / "docs" / "kronos_v6_universe_manifest_2026-07-19.json"
DEFAULT_START_YYYYMMDD = 20180101
DEFAULT_END_YYYYMMDD = 20260612
DEFAULT_HORIZONS = (1, 3, 5)
CSV_FIELDS = (
    "symbol", "table", "session_yyyymmdd", "split",
    "ret_1d_prev", "ret_5d_prev", "ret_20d_prev", "vol_z_20",
    "foreign_ratio_prev", "foreign_ratio_delta_5", "inst_netbuy_norm_5",
    "entry_close_1520", "future_return_h1_1520_proxy", "future_return_h3_1520_proxy",
    "future_return_h5_1520_proxy", "label_reason_h1", "label_reason_h3", "label_reason_h5",
)


def load_default_universe(manifest_path: Path | str = DEFAULT_UNIVERSE_MANIFEST_PATH) -> list[str]:
    """Load the table identities from the checked-in V6 universe manifest."""
    with Path(manifest_path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [str(item["table"]) for item in payload["universe"]]


def build_joined_dataset(
    universe: Sequence[str] | None = None,
    *,
    daily_db_path: Path | str = DEFAULT_DAILY_DB_PATH,
    fivemin_db_path: Path | str = daily_1520_source.DEFAULT_5MIN_DB_PATH,
    start_yyyymmdd: int = DEFAULT_START_YYYYMMDD,
    end_yyyymmdd: int = DEFAULT_END_YYYYMMDD,
    horizons: Iterable[int] = DEFAULT_HORIZONS,
    universe_manifest_path: Path | str | None = None,
) -> dict[str, Any]:
    """Join D-1 daily features to exact 15:20 rows without price fallbacks."""
    normalized_horizons = _validate_horizons(horizons)
    start = _coerce_yyyymmdd(start_yyyymmdd, "start_yyyymmdd")
    end = _coerce_yyyymmdd(end_yyyymmdd, "end_yyyymmdd")
    if start > end:
        raise ValueError("start_yyyymmdd must not be after end_yyyymmdd")

    manifest_used: Path | None = None
    if universe is None:
        manifest_used = Path(universe_manifest_path or DEFAULT_UNIVERSE_MANIFEST_PATH)
        tables = load_default_universe(manifest_used)
    else:
        tables = [str(table) for table in universe]
        if universe_manifest_path is not None:
            manifest_used = Path(universe_manifest_path)
    if len(set(tables)) != len(tables):
        raise ValueError("universe must not contain duplicate tables")

    rows: list[dict[str, Any]] = []
    missing_by_split = {split: {f"missing_h{h}_labels": 0 for h in normalized_horizons}
                        for split in ("train", "val", "test", "embargo_dropped")}
    missing_by_symbol: dict[str, dict[str, int]] = {}
    daily_path = Path(daily_db_path)
    with _connect_daily_readonly(daily_path) as conn:
        for table in sorted(tables):
            symbol = daily_1520_source.resolve_5min_table(table).symbol
            daily_rows = _read_daily_rows(conn, table)
            fills = daily_1520_source.read_exact_1520_rows(
                fivemin_db_path, table, start_date=start, end_date=end
            )
            rows.extend(_build_symbol_rows(
                symbol, table, daily_rows, fills, normalized_horizons, missing_by_split, missing_by_symbol
            ))

    rows.sort(key=lambda row: (row["symbol"], row["session_yyyymmdd"]))
    split_counts = {split: sum(row["split"] == split for row in rows)
                    for split in ("train", "val", "test", "embargo_dropped")}
    csv_bytes = _dataset_csv_bytes(rows, normalized_horizons)
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "schema_version": SCHEMA_VERSION,
        "universe": {
            "size": len(tables),
            "manifest_path": str(manifest_used) if manifest_used else None,
            "manifest_sha256": _sha256_file(manifest_used) if manifest_used else None,
        },
        "db_snapshot_stats": {
            "daily": _snapshot_stats(daily_path),
            "fivemin": _snapshot_stats(Path(fivemin_db_path)),
        },
        "features": [{"name": name, "timing": FEATURE_TIMING,
                      "daily_price_basis_caveat": DAILY_PRICE_BASIS_CAVEAT}
                     for name in CSV_FIELDS[4:11]],
        "label_policy": {
            "source": "exact_15_20_bars_only", "entry": "15:20 close proxy",
            "exit": "nth_following_observed_exact_15_20_session", "exit_gap_guard_calendar_days": "n*2+5",
            "missing_exit_reason": "missing_exit",
        },
        "horizons": list(normalized_horizons),
        "split_row_counts": split_counts,
        "per_split_missing_label_counts": missing_by_split,
        "per_symbol_missing_label_counts": missing_by_symbol,
        "false_research_locks": dict(daily_1520_source.FALSE_RESEARCH_LOCKS),
        "dataset_sha256": hashlib.sha256(csv_bytes).hexdigest(),
    }
    return {"rows": rows, "manifest": manifest}


def write_joined_dataset(
    universe: Sequence[str] | None = None,
    *,
    out_root: Path | str = Path("webui/rl_runs/v6_daily_h1"),
    run_id: str,
    daily_db_path: Path | str = DEFAULT_DAILY_DB_PATH,
    fivemin_db_path: Path | str = daily_1520_source.DEFAULT_5MIN_DB_PATH,
    start_yyyymmdd: int = DEFAULT_START_YYYYMMDD,
    end_yyyymmdd: int = DEFAULT_END_YYYYMMDD,
    horizons: Iterable[int] = DEFAULT_HORIZONS,
    universe_manifest_path: Path | str | None = None,
) -> dict[str, Any]:
    """Build and write a deterministic CSV plus its provenance manifest."""
    if not run_id or Path(run_id).name != run_id:
        raise ValueError("run_id must be a non-empty single path component")
    result = build_joined_dataset(
        universe, daily_db_path=daily_db_path, fivemin_db_path=fivemin_db_path,
        start_yyyymmdd=start_yyyymmdd, end_yyyymmdd=end_yyyymmdd, horizons=horizons,
        universe_manifest_path=universe_manifest_path,
    )
    destination = Path(out_root) / run_id
    destination.mkdir(parents=True, exist_ok=True)
    dataset_path = destination / "dataset.csv"
    dataset_path.write_bytes(_dataset_csv_bytes(result["rows"], tuple(result["manifest"]["horizons"])))
    result["manifest"]["generated_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result["manifest"]["dataset_sha256"] = _sha256_file(dataset_path)
    manifest_path = destination / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(result["manifest"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["dataset_path"] = dataset_path
    result["manifest_path"] = manifest_path
    return result


def _build_symbol_rows(
    symbol: str,
    table: str,
    daily_rows: list[dict[str, Any]],
    fills: Sequence[Any],
    horizons: tuple[int, ...],
    missing_by_split: dict[str, dict[str, int]],
    missing_by_symbol: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    sessions = [_coerce_yyyymmdd(str(fill.timestamp_yyyymmddhhmm)[:8], "fill session") for fill in fills]
    if sessions != sorted(sessions) or len(set(sessions)) != len(sessions):
        raise ValueError(f"exact-15:20 sessions for {table} must be unique and ordered")
    output: list[dict[str, Any]] = []
    missing_by_symbol[symbol] = {f"missing_h{h}_labels": 0 for h in horizons}
    max_horizon = max(horizons)
    for index, (fill, session) in enumerate(zip(fills, sessions)):
        previous = [row for row in daily_rows if row["date"] < session]
        row: dict[str, Any] = {
            "symbol": symbol, "table": table, "session_yyyymmdd": session,
            **_features(previous), "entry_close_1520": _number(fill.close, "15:20 close"),
        }
        split = _base_split(session)
        max_exit_session = sessions[index + max_horizon] if index + max_horizon < len(sessions) else None
        if max_exit_session is not None and _base_split(max_exit_session) != split:
            split = "embargo_dropped"
        row["split"] = split
        for horizon in horizons:
            label, reason = _label(fills, sessions, index, horizon)
            row[f"future_return_h{horizon}_1520_proxy"] = label
            row[f"label_reason_h{horizon}"] = reason
            if reason == "missing_exit":
                missing_by_split[split][f"missing_h{horizon}_labels"] += 1
                missing_by_symbol[symbol][f"missing_h{horizon}_labels"] += 1
        output.append(row)
    return output


def _features(rows: Sequence[dict[str, Any]]) -> dict[str, float | None]:
    closes = [row["close"] for row in rows]
    volumes = [row["volume"] for row in rows]
    foreign = [row["foreign"] for row in rows]
    inst = [row["inst"] for row in rows]
    shares = [row["shares"] for row in rows]
    return {
        "ret_1d_prev": _return(closes, 1), "ret_5d_prev": _return(closes, 5),
        "ret_20d_prev": _return(closes, 20), "vol_z_20": _zscore_last(volumes, 20),
        "foreign_ratio_prev": foreign[-1] if foreign else None,
        "foreign_ratio_delta_5": _delta(foreign, 5),
        "inst_netbuy_norm_5": _normalized_sum(inst, 5, shares[-1] if shares else None),
    }


def _label(fills: Sequence[Any], sessions: Sequence[int], index: int, horizon: int) -> tuple[float | None, str | None]:
    exit_index = index + horizon
    if exit_index >= len(fills) or _calendar_days(sessions[index], sessions[exit_index]) > horizon * 2 + 5:
        return None, "missing_exit"
    entry = _number(fills[index].close, "15:20 close")
    exit_close = _number(fills[exit_index].close, "15:20 close")
    if entry == 0:
        return None, "zero_entry_close"
    return exit_close / entry - 1.0, None


def _read_daily_rows(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    quoted = _quote_table(table)
    try:
        source_rows = conn.execute(
            f'SELECT date, close, volume, "상장주식수", "외국인현보유비율", "기관순매수" FROM {quoted} ORDER BY date'
        ).fetchall()
    except sqlite3.Error as exc:
        raise ValueError(f"daily table {table} lacks required V6 columns") from exc
    rows = []
    for source in source_rows:
        rows.append({"date": _coerce_yyyymmdd(source[0], "daily date"), "close": _number_or_none(source[1]),
                     "volume": _number_or_none(source[2]), "shares": _number_or_none(source[3]),
                     "foreign": _number_or_none(source[4]), "inst": _number_or_none(source[5])})
    if len({row["date"] for row in rows}) != len(rows):
        raise ValueError(f"daily table {table} has duplicate dates")
    return sorted(rows, key=lambda row: row["date"])


def _connect_daily_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def _quote_table(table: str) -> str:
    daily_1520_source.resolve_5min_table(table)
    return '"' + table + '"'


def _return(values: Sequence[float | None], periods: int) -> float | None:
    if len(values) <= periods or values[-1] is None or values[-1 - periods] in (None, 0):
        return None
    return values[-1] / values[-1 - periods] - 1.0  # type: ignore[operator]


def _delta(values: Sequence[float | None], periods: int) -> float | None:
    if len(values) <= periods or values[-1] is None or values[-1 - periods] is None:
        return None
    return values[-1] - values[-1 - periods]  # type: ignore[operator]


def _zscore_last(values: Sequence[float | None], size: int) -> float | None:
    window = values[-size:]
    if len(window) != size or any(value is None for value in window):
        return None
    numbers = [float(value) for value in window if value is not None]
    mean = sum(numbers) / size
    stddev = math.sqrt(sum((value - mean) ** 2 for value in numbers) / size)
    return None if stddev == 0 else (numbers[-1] - mean) / stddev


def _normalized_sum(values: Sequence[float | None], size: int, denominator: float | None) -> float | None:
    window = values[-size:]
    if len(window) != size or denominator in (None, 0) or any(value is None for value in window):
        return None
    return sum(float(value) for value in window if value is not None) / denominator


def _base_split(session: int) -> str:
    if session <= 20231231:
        return "train"
    if session <= 20250630:
        return "val"
    return "test"


def _calendar_days(first: int, second: int) -> int:
    return (datetime.strptime(str(second), "%Y%m%d") - datetime.strptime(str(first), "%Y%m%d")).days


def _coerce_yyyymmdd(value: Any, name: str) -> int:
    text = str(value).replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"{name} must be YYYYMMDD")
    datetime.strptime(text, "%Y%m%d")
    return int(text)


def _number(value: Any, name: str) -> float:
    number = _number_or_none(value)
    if number is None:
        raise ValueError(f"{name} must be numeric and non-null")
    return number


def _number_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"numeric value required, got {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"finite numeric value required, got {value!r}")
    return number


def _validate_horizons(horizons: Iterable[int]) -> tuple[int, ...]:
    values = tuple(sorted(set(horizons)))
    if not values or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
        raise ValueError("horizons must be non-empty positive integers")
    return values


def _dataset_csv_bytes(rows: Sequence[dict[str, Any]], horizons: tuple[int, ...]) -> bytes:
    fields = tuple(field for field in CSV_FIELDS if not field.startswith("future_return_h") and not field.startswith("label_reason_h"))
    label_fields = tuple(item for horizon in horizons for item in
                         (f"future_return_h{horizon}_1520_proxy", f"label_reason_h{horizon}"))
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=[*fields, *label_fields], lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in writer.fieldnames})
    return buffer.getvalue().encode("utf-8")


def _snapshot_stats(path: Path) -> dict[str, Any]:
    info = path.stat()
    return {"path_suffix": path.suffix, "size_bytes": info.st_size, "mtime_ns": info.st_mtime_ns}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the research-only V6 joined daily dataset.")
    parser.add_argument("--universe-limit", type=int)
    parser.add_argument("--start", type=int, default=DEFAULT_START_YYYYMMDD)
    parser.add_argument("--end", type=int, default=DEFAULT_END_YYYYMMDD)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-root", default="webui/rl_runs/v6_daily_h1")
    args = parser.parse_args()
    universe = load_default_universe()
    if args.universe_limit is not None:
        universe = universe[:args.universe_limit]
    result = write_joined_dataset(universe, out_root=args.out_root, run_id=args.run_id,
                                  start_yyyymmdd=args.start, end_yyyymmdd=args.end)
    print(json.dumps({"dataset_path": str(result["dataset_path"]), "dataset_sha256": result["manifest"]["dataset_sha256"]}))


if __name__ == "__main__":
    main()
