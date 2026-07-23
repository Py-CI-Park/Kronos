"""Fail-closed materializer for the replacement Type 1 public dataset.

Only the signed KRX authority supplies symbols and sessions.  This module never
opens fresh OOS data and never falls back to a heuristic universe or a nearest
bar/official-close price.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Context, Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
import hashlib
import json
import stat
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Sequence

from stom_rl import daily_1520_source
from stom_rl.daily_type1_authority import AuthorityError, load_type1_authority
from stom_rl.daily_type1_contract import FEATURES, canonical_json_bytes
from stom_rl.daily_type1_market import (
    REUSED_VALIDATION_END, REUSED_VALIDATION_START, TRAIN_END, TRAIN_START,
    public_row_from_mapping,
)

DATASET_ID = "type1-close-20260803-003"
PUBLIC_CUTOFF = 20250630
PUBLIC_START = 20180102
PROXY_HHMM = 1520
SCHEMA_VERSION = "kronos_type1_g002_public_data.v3"
REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "docs" / "kronos_type1_g002_public_protocol_2026-07-23.json"
PREREG_PATH = REPO_ROOT / "docs" / "kronos_type1_closing_prereg_2026-07-23.json"
AMENDMENT_PATH = REPO_ROOT / "docs" / "kronos_type1_g002_recovery_amendment_v2_2026-07-23.json"
DEFAULT_AUTHORITY_PATH = REPO_ROOT / "artifacts" / "type1-authority" / "type1-krx-authority-20260723-002.json"
AUTHORITY_ID = "type1-krx-authority-20260723-002"
MATERIALIZER_MANIFEST_SCHEMA = "kronos.type1.public-materializer.v3"
_DECIMAL_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)
_DAILY_COLUMNS = ("date", "close", "volume", "상장주식수", "외국인현보유비율", "기관순매수")
_FIVE_MIN_COLUMNS = ("date", "open", "high", "low", "close", "volume")


def materialize_public_data(
    *,
    daily_db_path: Path | str,
    fivemin_db_path: Path | str,
    authority_path: Path | str = DEFAULT_AUTHORITY_PATH,
    expected_source_identities: Mapping[str, Mapping[str, Any]] | None = None,
    authority: Mapping[str, Any] | None = None,
    test_only: bool = False,
) -> dict[str, Any]:
    """Materialize only authority-listed symbols and sessions from fixed sources.

    ``authority`` is an intentionally test-only injection seam.  Production
    always verifies the signed authority file and requires independently pinned
    source file identities; it cannot approve identities it just observed.
    """
    amendment = _load_amendment()
    verified_authority, authority_receipt = _load_authority(authority_path, authority, test_only)
    symbols, split_sessions, split_calendar = _authority_calendar(verified_authority, test_only=test_only)
    daily_path = _safe_source_path(daily_db_path, "daily")
    five_path = _safe_source_path(fivemin_db_path, "fivemin")
    _reject_combined_sources(daily_path, five_path)
    before = {"daily": _file_receipt(daily_path), "fivemin": _file_receipt(five_path)}
    expected = _expected_source_identities(expected_source_identities, before, test_only=test_only)
    _assert_expected_identities(expected, before)

    per_split_rows: dict[str, list[dict[str, Any]]] = {"train": [], "reused_validation": []}
    missing_labels: dict[str, int] = {"train": 0, "reused_validation": 0}
    missing_by_symbol: dict[str, dict[str, int]] = {}
    all_sessions = {session for values in split_sessions.values() for session in values}
    with _connect_readonly(daily_path) as daily_conn, _connect_readonly(five_path) as five_conn:
        for symbol in symbols:
            ref = daily_1520_source.resolve_5min_table(symbol)
            daily_rows: list[dict[str, Decimal | None | int]] = []
            fills: dict[str, Decimal] = {}
            if _table_exists(daily_conn, ref.table):
                _require_columns(daily_conn, ref.table, _DAILY_COLUMNS, "daily")
                daily_rows = _read_daily_rows(daily_conn, ref.table, all_sessions)
            if _table_exists(five_conn, ref.table):
                _require_columns(five_conn, ref.table, _FIVE_MIN_COLUMNS, "5-minute")
                fills = _read_exact_1520_rows(five_conn, ref.table, all_sessions)
            rows, misses = _build_symbol_rows(ref.symbol, daily_rows, fills, split_sessions, split_calendar)
            missing_by_symbol[ref.symbol] = misses
            for split, count in misses.items():
                missing_labels[split] += count
            for row in rows:
                per_split_rows[row["split"]].append(row)
    after = {"daily": _file_receipt(daily_path), "fivemin": _file_receipt(five_path)}
    _assert_expected_identities(expected, after)
    if before != after:
        raise ValueError("source database changed during materialization")
    if authority is None:
        if _file_receipt(_safe_source_path(authority_path, "authority")) != {key: value for key, value in authority_receipt.items() if key != "test_only_injected"}:
            raise ValueError("authority artifact changed during materialization")

    rows = sorted((row for split_rows in per_split_rows.values() for row in split_rows), key=lambda row: (row["decision_date"], row["symbol"]))
    _validate_cartesian_rows(rows, symbols, split_sessions, split_calendar)
    for row in rows:
        public_row_from_mapping({key: value for key, value in _public_schema(row).items() if key != "split"})
    serialized_rows = [_public_schema(row) for row in rows]
    row_bytes = canonical_json_bytes(serialized_rows)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "materializer_manifest_schema": MATERIALIZER_MANIFEST_SCHEMA,
        "dataset_id": DATASET_ID,
        "read_only": True,
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
        "public_cutoff": "2025-06-30",
        "sql_predicates": {
            "daily": "CAST(date AS INTEGER) <= 20250630",
            "exact_1520": "CAST(date AS INTEGER) >= 201801021520 AND CAST(date AS INTEGER) <= 202506302359 AND CAST(date AS INTEGER) % 10000 = 1520",
        },
        "source_databases": {"expected": expected, "before": before, "after": after, "observed": after},
        "source_database_identity": expected,
        "authority": {
            "authority_id": AUTHORITY_ID,
            "artifact": authority_receipt,
            "anchor_date": verified_authority["anchor_date"],
            "raw_sha256": verified_authority["raw_sha256"],
            "ranking": dict(verified_authority["ranking"]),
            "provider": dict(verified_authority["provider"]),
            "query_profile": dict(verified_authority["query_profile"]),
            "stable_symbols": list(symbols),
            "sessions": split_calendar,
        },
        "row_count": len(serialized_rows),
        "split_row_counts": {split: len(values) for split, values in per_split_rows.items()},
        "split_symbol_counts": {split: len({row["symbol"] for row in values}) for split, values in per_split_rows.items()},
        "expected": {
            "stable_symbols": len(symbols),
            "split_rows": {split: len(symbols) * len(sessions) for split, sessions in split_sessions.items()},
            "split_pairs": {split: len(calendar["pairs"]) for split, calendar in split_calendar.items()},
            "split_embargo": {split: len(calendar["trailing_embargo"]) for split, calendar in split_calendar.items()},
        },
        "missing_h1_label_counts": missing_labels,
        "missing_h1_by_symbol": missing_by_symbol,
        "output_sha256": hashlib.sha256(row_bytes).hexdigest(),
        "protocol_sha256": _sha256_file(PROTOCOL_PATH),
        "parent_protocol_sha256": _sha256_file(PROTOCOL_PATH),
        "prereg_sha256": _sha256_file(PREREG_PATH),
        "preregistration_sha256": _sha256_file(PREREG_PATH),
        "amendment_sha256": _sha256_file(AMENDMENT_PATH),
        "authority_sha256": authority_receipt["sha256"],
        "amendment_id": amendment["amendment_id"],
        "materializer_source_sha256": _sha256_file(Path(__file__)),
        "source_hashes": {
            "materializer": _sha256_file(Path(__file__)),
            "protocol": _sha256_file(PROTOCOL_PATH),
            "preregistration": _sha256_file(PREREG_PATH),
            "amendment": _sha256_file(AMENDMENT_PATH),
            "authority": authority_receipt["sha256"],
        },
        "fresh_oos": {"state": "NOT_RUN", "read_performed": False},
    }
    return {"rows": serialized_rows, "manifest": manifest, "rows_bytes": row_bytes}


def write_public_materialization(*, out_root: Path | str, **kwargs: Any) -> dict[str, Any]:
    result = materialize_public_data(**kwargs)
    root = Path(out_root)
    _reject_path_indirection(root)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / DATASET_ID
    destination.mkdir()  # output reuse is a scientific identity violation
    rows_path, manifest_path = destination / "public_rows.json", destination / "dataset_manifest.json"
    with rows_path.open("xb") as handle:
        handle.write(result["rows_bytes"])
    with manifest_path.open("xb") as handle:
        handle.write(canonical_json_bytes(result["manifest"]))
    return {**result, "destination": destination, "rows_path": rows_path, "manifest_path": manifest_path}


def _load_amendment() -> Mapping[str, Any]:
    value = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
    required = {
        "schema_version", "amendment_id", "supersedes", "status", "reason",
        "preserved_aborted_evidence", "replacement_identity", "authority_contract",
        "execution_contract", "fresh_oos", "frozen_utc",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError("recovery amendment v2 schema mismatch")
    replacement = value["replacement_identity"]
    expected = {
        "authority_id": AUTHORITY_ID,
        "dataset_id": DATASET_ID,
        "train_id": "type1-public-003",
        "train_run_id": "train_type1-public-003",
        "custody_uid": "type1-fresh-oos-20260803-003",
    }
    if value["schema_version"] != "kronos.type1.g002-recovery-amendment.v2" or replacement != expected:
        raise ValueError("recovery amendment does not authorize this replacement identity")
    if value["fresh_oos"] != {"custody_uid": expected["custody_uid"], "status": "NOT_RUN", "no_read": True, "no_price_or_oos_query_after": "2025-06-30"}:
        raise ValueError("recovery amendment fresh-OOS state is unsafe")
    if value["execution_contract"] != {"proxy_time": "15:20:00", "cost_bps": 23, "fixed_notional": 60000000, "primary_seeds": 5, "shuffled_seeds": 5, "timesteps_per_seed": 200000, "outcome": "NO_GO_ONLY"}:
        raise ValueError("recovery amendment execution contract mismatch")
    return value


def _load_authority(path: Path | str, injected: Mapping[str, Any] | None, test_only: bool) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    if injected is not None:
        if not test_only:
            raise ValueError("injected authority is allowed only in test_only mode")
        required = {"stable_symbols", "sessions", "anchor_date", "ranking", "provider", "query_profile", "raw_sha256"}
        if not required <= set(injected):
            raise ValueError("test authority lacks required projection")
        return injected, {"test_only_injected": True, "sha256": hashlib.sha256(canonical_json_bytes(injected)).hexdigest()}
    artifact = _safe_source_path(path, "authority")
    try:
        loaded = load_type1_authority(artifact)
    except AuthorityError as exc:
        raise ValueError("KRX authority verification failed") from exc
    return loaded, {"test_only_injected": False, **_file_receipt(artifact)}


def _authority_calendar(authority: Mapping[str, Any], *, test_only: bool) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]], dict[str, Any]]:
    symbols = tuple(authority["stable_symbols"])
    if (not test_only and len(symbols) != 500) or not symbols or len(set(symbols)) != len(symbols) or any(not isinstance(item, str) or len(item) != 6 or not item.isdigit() for item in symbols):
        raise ValueError("authority stable symbols are invalid")
    sessions = authority["sessions"]
    ordered = tuple(sessions["ordered"])
    if not ordered or tuple(sorted(ordered)) != ordered or len(set(ordered)) != len(ordered):
        raise ValueError("authority sessions are not ordered and unique")
    expected_pairs = [[index, index + 1] for index in range(0, len(ordered) - 1, 2)]
    expected_embargo = [len(ordered) - 1] if len(ordered) % 2 else []
    actual_pairs = [list(pair) for pair in sessions.get("pairs", ())]
    actual_embargo = list(sessions.get("trailing_embargo", ()))
    if actual_pairs != expected_pairs or actual_embargo != expected_embargo:
        raise ValueError("authority pair/calendar metadata is misaligned")
    if any(_session_number(item) > PUBLIC_CUTOFF or _session_number(item) < PUBLIC_START for item in ordered):
        raise ValueError("authority sessions exceed public bounds")
    split_sessions = {"train": tuple(item for item in ordered if _split_for(_session_number(item)) == "train"), "reused_validation": tuple(item for item in ordered if _split_for(_session_number(item)) == "reused_validation")}
    if sum(map(len, split_sessions.values())) != len(ordered):
        raise ValueError("authority calendar does not align with frozen splits")
    result: dict[str, Any] = {}
    for split, values in split_sessions.items():
        pairs = [[index, index + 1] for index in range(0, len(values) - 1, 2)]
        embargo = [len(values) - 1] if len(values) % 2 else []
        result[split] = {"ordered": list(values), "pairs": pairs, "trailing_embargo": embargo}
    return symbols, split_sessions, result


def _safe_source_path(value: Path | str, label: str) -> Path:
    path = Path(value)
    if not path.is_file():
        raise FileNotFoundError(path)
    _reject_path_indirection(path)
    return path.resolve(strict=True)


def _reject_path_indirection(path: Path) -> None:
    current = path.absolute()
    for candidate in (current, *current.parents):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if candidate.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise ValueError("symlink or reparse path is not permitted")


def _reject_combined_sources(daily: Path, five: Path) -> None:
    left, right = daily.stat(), five.stat()
    if daily == five or (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino):
        raise ValueError("combined daily/5-minute source is not permitted")


def _expected_source_identities(value: Mapping[str, Mapping[str, Any]] | None, observed: Mapping[str, Mapping[str, Any]], *, test_only: bool) -> dict[str, dict[str, Any]]:
    if value is None:
        if not test_only:
            raise ValueError("production requires fixed expected_source_identities")
        return {key: _identity_projection(item) for key, item in observed.items()}
    if set(value) != {"daily", "fivemin"}:
        raise ValueError("expected source identities must name daily and fivemin")
    return {key: _identity_projection(value[key]) for key in ("daily", "fivemin")}


def _identity_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"sha256", "size_bytes", "mtime_ns"}:
        raise ValueError("source identity must contain only sha256, size_bytes, mtime_ns")
    if not isinstance(value["sha256"], str) or len(value["sha256"]) != 64 or any(char not in "0123456789abcdef" for char in value["sha256"]):
        raise ValueError("source identity sha256 is invalid")
    if type(value["size_bytes"]) is not int or value["size_bytes"] < 0 or type(value["mtime_ns"]) is not int or value["mtime_ns"] < 0:
        raise ValueError("source identity metadata is invalid")
    return dict(value)


def _assert_expected_identities(expected: Mapping[str, Mapping[str, Any]], observed: Mapping[str, Mapping[str, Any]]) -> None:
    for key, identity in expected.items():
        if _identity_projection(observed[key]) != dict(identity):
            raise ValueError(f"fixed {key} source identity changed")


def _connect_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def _quote(table: str) -> str:
    return '"' + table + '"'
def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None



def _require_columns(conn: sqlite3.Connection, table: str, expected: tuple[str, ...], label: str) -> None:
    columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({_quote(table)})")}
    missing = [column for column in expected if column not in columns]
    if missing:
        raise ValueError(f"{label} table {table} lacks required columns {missing}")


def _read_daily_rows(conn: sqlite3.Connection, table: str, authority_sessions: set[str]) -> list[dict[str, Decimal | None | int]]:
    source = conn.execute(f'SELECT date, close, volume, "상장주식수", "외국인현보유비율", "기관순매수" FROM {_quote(table)} WHERE CAST(date AS INTEGER) <= ? ORDER BY CAST(date AS INTEGER), rowid', (PUBLIC_CUTOFF,)).fetchall()
    rows = []
    for item in source:
        session = _canonical_date(item[0], "daily date")
        if PUBLIC_START <= _session_number(session) <= PUBLIC_CUTOFF and session not in authority_sessions:
            raise ValueError("daily source contains a non-authoritative session")
        rows.append({"date": _date_value(session), "close": _decimal_or_none(item[1]), "volume": _decimal_or_none(item[2]), "shares": _decimal_or_none(item[3]), "foreign": _decimal_or_none(item[4]), "inst": _decimal_or_none(item[5])})
    if len({row["date"] for row in rows}) != len(rows):
        raise ValueError(f"daily table {table} has duplicate dates")
    return rows


def _read_exact_1520_rows(conn: sqlite3.Connection, table: str, authority_sessions: set[str]) -> dict[str, Decimal]:
    source = conn.execute(f"SELECT date, close FROM {_quote(table)} WHERE CAST(date AS INTEGER) >= ? AND CAST(date AS INTEGER) <= ? AND CAST(date AS INTEGER) % 10000 = ? ORDER BY CAST(date AS INTEGER), rowid", (PUBLIC_START * 10000, PUBLIC_CUTOFF * 10000 + 2359, PROXY_HHMM)).fetchall()
    fills: dict[str, Decimal] = {}
    for item in source:
        timestamp = item[0]
        if type(timestamp) is not int or timestamp % 10000 != PROXY_HHMM:
            raise ValueError("exact 15:20 source timestamp is malformed")
        session = _canonical_date(timestamp // 10000, "15:20 session")
        if session not in authority_sessions:
            raise ValueError("15:20 source contains a non-authoritative session")
        if session in fills:
            raise ValueError(f"5-minute table {table} has duplicate exact-15:20 sessions")
        fills[session] = _decimal_required(item[1], "15:20 close")
    return fills


def _build_symbol_rows(symbol: str, daily: Sequence[Mapping[str, Any]], fills: Mapping[str, Decimal], split_sessions: Mapping[str, Sequence[str]], split_calendar: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    ordered_daily = sorted(daily, key=lambda row: row["date"])
    daily_index = 0
    history: list[Mapping[str, Any]] = []
    output: list[dict[str, Any]] = []
    missing = {"train": 0, "reused_validation": 0}
    for split, sessions in split_sessions.items():
        pair_by_decision = {sessions[left]: sessions[right] for left, right in split_calendar[split]["pairs"]}
        for session in sessions:
            while daily_index < len(ordered_daily) and ordered_daily[daily_index]["date"].isoformat() < session:
                history.append(ordered_daily[daily_index])
                daily_index += 1
                if len(history) > 25:
                    history.pop(0)
            entry = fills.get(session)
            settlement = pair_by_decision.get(session)
            gross_return = None
            available = entry is not None
            if settlement is not None and entry not in (None, Decimal(0)) and fills.get(settlement) is not None:
                gross_return = fills[settlement] / entry - Decimal(1)
            else:
                missing[split] += 1
            output.append({"decision_date": session, "symbol": symbol, "split": split, "features": _features(history), "gross_return": gross_return, "entry_available": available})
    return output, missing


def _features(rows: Sequence[Mapping[str, Any]]) -> dict[str, Decimal | None]:
    closes, volumes = [row["close"] for row in rows], [row["volume"] for row in rows]
    foreign, inst, shares = [row["foreign"] for row in rows], [row["inst"] for row in rows], [row["shares"] for row in rows]
    return {"ret_1d_prev": _return(closes, 1), "ret_5d_prev": _return(closes, 5), "ret_20d_prev": _return(closes, 20), "vol_z_20": _zscore(volumes), "foreign_ratio_prev": foreign[-1] if foreign else None, "foreign_ratio_delta_5": _delta(foreign, 5), "inst_netbuy_norm_5": _normalized_sum(inst, shares[-1] if shares else None)}


def _return(values: Sequence[Decimal | None], periods: int) -> Decimal | None:
    return None if len(values) <= periods or values[-1] is None or values[-1 - periods] in (None, Decimal(0)) else values[-1] / values[-1 - periods] - Decimal(1)


def _delta(values: Sequence[Decimal | None], periods: int) -> Decimal | None:
    return None if len(values) <= periods or values[-1] is None or values[-1 - periods] is None else values[-1] - values[-1 - periods]


def _zscore(values: Sequence[Decimal | None]) -> Decimal | None:
    window = values[-20:]
    if len(window) != 20 or any(value is None for value in window): return None
    with localcontext(_DECIMAL_CONTEXT):
        mean = sum(window, Decimal(0)) / Decimal(20)  # type: ignore[arg-type]
        variance = sum((value - mean) ** 2 for value in window if value is not None) / Decimal(20)
        return None if variance == 0 else (window[-1] - mean) / variance.sqrt()  # type: ignore[operator]


def _normalized_sum(values: Sequence[Decimal | None], denominator: Decimal | None) -> Decimal | None:
    window = values[-5:]
    return None if len(window) != 5 or denominator in (None, Decimal(0)) or any(value is None for value in window) else sum((value for value in window if value is not None), Decimal(0)) / denominator


def _split_for(session: int) -> str | None:
    current = _date_value(session)
    if TRAIN_START <= current <= TRAIN_END: return "train"
    if REUSED_VALIDATION_START <= current <= REUSED_VALIDATION_END: return "reused_validation"
    return None


def _validate_cartesian_rows(
    rows: Sequence[Mapping[str, Any]],
    symbols: Sequence[str],
    split_sessions: Mapping[str, Sequence[str]],
    split_calendar: Mapping[str, Mapping[str, Any]],
) -> None:
    expected = {
        (split, session, symbol)
        for split, sessions in split_sessions.items()
        for session in sessions
        for symbol in symbols
    }
    observed = [(row["split"], row["decision_date"], row["symbol"]) for row in rows]
    if len(observed) != len(set(observed)):
        raise ValueError("materializer rows contain duplicate full Cartesian keys")
    if set(observed) != expected:
        raise ValueError("materializer rows are not the exact authority Cartesian product")
    for split, sessions in split_sessions.items():
        if len({row["symbol"] for row in rows if row["split"] == split}) != len(symbols):
            raise ValueError("materializer split does not contain all authority symbols")
        calendar = split_calendar[split]
        if len(calendar["pairs"]) != len(sessions) // 2 or len(calendar["trailing_embargo"]) != len(sessions) % 2:
            raise ValueError("materializer split pair or embargo count differs from authority")
    if [key[1:] for key in observed] != sorted((key[1:] for key in observed)):
        raise ValueError("materializer rows are not canonically ordered before normalization")
def _public_schema(row: Mapping[str, Any]) -> dict[str, Any]:
    return {"decision_date": row["decision_date"], "symbol": row["symbol"], "split": row["split"], "features": {name: _decimal_text(row["features"][name]) for name in FEATURES}, "gross_return": _decimal_text(row["gross_return"]), "entry_available": row["entry_available"]}


def _canonical_date(value: Any, label: str) -> str:
    if type(value) is not int: raise ValueError(f"{label} must be canonical integer YYYYMMDD")
    return _date_value(value).isoformat()


def _session_number(value: str) -> int:
    return int(value.replace("-", ""))


def _date_value(value: Any) -> date:
    raw = str(value).replace("-", "")
    if len(raw) != 8 or not raw.isdigit(): raise ValueError("daily date must be YYYYMMDD")
    return date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))


def _decimal_or_none(value: Any) -> Decimal | None:
    return None if value is None else _decimal_required(value, "numeric value")


def _decimal_required(value: Any, name: str) -> Decimal:
    if isinstance(value, bool): raise ValueError(f"{name} must be finite")
    try: result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc: raise ValueError(f"{name} must be finite") from exc
    if not result.is_finite(): raise ValueError(f"{name} must be finite")
    return result


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()


def _file_receipt(path: Path) -> dict[str, Any]:
    info = path.stat()
    return {"sha256": _sha256_file(path), "size_bytes": info.st_size, "mtime_ns": info.st_mtime_ns}


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize only the signed Type 1 KRX public authority.")
    parser.add_argument("--daily-db", required=True)
    parser.add_argument("--fivemin-db", required=True)
    parser.add_argument("--authority", required=True)
    parser.add_argument("--source-identities-json", required=True)
    parser.add_argument("--out-root", required=True)
    args = parser.parse_args()
    identities = json.loads(Path(args.source_identities_json).read_text(encoding="utf-8"))
    result = write_public_materialization(out_root=args.out_root, daily_db_path=args.daily_db, fivemin_db_path=args.fivemin_db, authority_path=args.authority, expected_source_identities=identities)
    print(json.dumps({"dataset_id": DATASET_ID, "rows_path": str(result["rows_path"]), "output_sha256": result["manifest"]["output_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
