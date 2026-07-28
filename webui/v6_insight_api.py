"""Read-only V6 daily-data insight API for research observation."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import sqlite3
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Final, Mapping

from flask import Blueprint, Response, request

WEBUI_ROOT: Final = Path(__file__).resolve().parent
REPO_ROOT: Final = WEBUI_ROOT.parent
DAILY_DB_PATH: Path = REPO_ROOT / "_database" / "Stock_Database_ohlcv_1day.db"
UNIVERSE_MANIFEST_PATH: Path = REPO_ROOT / "docs" / "kronos_v6_universe_manifest_2026-07-19.json"
ALL_ROUTE_METHODS: Final = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
CODE_PATTERN: Final = re.compile(r"^[0-9]{6}$")
TABLE_PATTERN: Final = re.compile(r"^A[0-9]{6}$")
PRICE_BASIS_CAVEAT: Final = "daily DB price basis UNKNOWN_CONFIRMED; observation only, not return evidence"
FLOW_CAVEAT: Final = "point-in-time publication lag unverified"
_CACHE_DEFAULT_MAX_ENTRIES: Final = 32
_CACHE_LOCK = threading.RLock()
_CACHE_ENTRY_LIMIT = _CACHE_DEFAULT_MAX_ENTRIES
_CACHE_REVISION: tuple[str | None, tuple[tuple[int, int] | None, ...]] | None = None
_CACHE_ENTRIES: OrderedDict[tuple[str, int, int], dict[str, Any]] = OrderedDict()
INDEX_BLOCKER_REGIME: Final = {"state": "BLOCKED_INDEX_SERIES_SOURCE", "reason": "KRX credentials required for pykrx collection"}


def _response(payload: Mapping[str, Any], status_code: int = 200) -> Response:
    return Response(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), status=status_code, mimetype="application/json")


def _error(status_code: int, code: str) -> Response:
    return _response({"status": "ERROR", "error": {"code": code}}, status_code)


def _method_not_allowed() -> Response:
    response = _error(405, "METHOD_NOT_ALLOWED")
    response.headers["Allow"] = "GET"
    return response


def _database_signature() -> tuple[tuple[int, int] | None, ...]:
    signatures: list[tuple[int, int] | None] = []
    for path in (DAILY_DB_PATH, Path(f"{DAILY_DB_PATH}-wal"), Path(f"{DAILY_DB_PATH}-shm")):
        try:
            stat = path.stat()
        except OSError:
            signatures.append(None)
        else:
            signatures.append((stat.st_mtime_ns, stat.st_size))
    return tuple(signatures)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(f"{DAILY_DB_PATH.resolve().as_uri()}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only = ON")
    return connection


def _manifest_snapshot() -> tuple[list[str] | None, str | None]:
    try:
        contents = UNIVERSE_MANIFEST_PATH.read_bytes()
    except OSError:
        return None, None
    digest = hashlib.sha256(contents).hexdigest()
    try:
        value = json.loads(contents)
    except (UnicodeDecodeError, ValueError):
        return None, digest
    if not isinstance(value, Mapping) or not isinstance(value.get("universe"), list):
        return None, digest
    tables: list[str] = []
    for item in value["universe"]:
        table = item.get("table") if isinstance(item, Mapping) else None
        if isinstance(table, str) and TABLE_PATTERN.fullmatch(table):
            tables.append(table)
    return tables, digest
def _cache_snapshot() -> tuple[list[str] | None, tuple[str | None, tuple[tuple[int, int] | None, ...]]]:
    tables, manifest_digest = _manifest_snapshot()
    return tables, (manifest_digest, _database_signature())


def reset_v6_insight_cache(*, max_entries: int | None = None) -> None:
    """Clear cached insight payloads; optional capacity is intended for tests."""
    if max_entries is not None and (not isinstance(max_entries, int) or isinstance(max_entries, bool) or max_entries < 1):
        raise ValueError("max_entries must be a positive integer")
    with _CACHE_LOCK:
        global _CACHE_ENTRY_LIMIT, _CACHE_REVISION
        _CACHE_ENTRY_LIMIT = _CACHE_DEFAULT_MAX_ENTRIES if max_entries is None else max_entries
        _CACHE_REVISION = None
        _CACHE_ENTRIES.clear()


def v6_insight_cache_stats() -> dict[str, Any]:
    """Return a stable cache summary without exposing mutable cache contents."""
    with _CACHE_LOCK:
        flow_entries = sum(key[0] == "flow" for key in _CACHE_ENTRIES)
        regime_entries = sum(key[0] == "regime" for key in _CACHE_ENTRIES)
        return {
            "revision": _CACHE_REVISION,
            "generation_count": int(_CACHE_REVISION is not None),
            "entry_count": len(_CACHE_ENTRIES),
            "entry_keys": tuple(_CACHE_ENTRIES),
            "flow_entries": flow_entries,
            "regime_entries": regime_entries,
            "max_entries": _CACHE_ENTRY_LIMIT,
        }


def _cache_activate(revision: tuple[str | None, tuple[tuple[int, int] | None, ...]]) -> None:
    with _CACHE_LOCK:
        global _CACHE_REVISION
        if _CACHE_REVISION != revision:
            _CACHE_REVISION = revision
            _CACHE_ENTRIES.clear()


def _cache_get(revision: tuple[str | None, tuple[tuple[int, int] | None, ...]], key: tuple[str, int, int]) -> dict[str, Any] | None:
    _cache_activate(revision)
    with _CACHE_LOCK:
        payload = _CACHE_ENTRIES.get(key)
        if payload is None:
            return None
        _CACHE_ENTRIES.move_to_end(key)
        return copy.deepcopy(payload)


def _cache_store(
    revision: tuple[str | None, tuple[tuple[int, int] | None, ...]],
    key: tuple[str, int, int],
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    with _CACHE_LOCK:
        if _CACHE_REVISION != revision:
            return None
        _CACHE_ENTRIES[key] = copy.deepcopy(payload)
        _CACHE_ENTRIES.move_to_end(key)
        while len(_CACHE_ENTRIES) > _CACHE_ENTRY_LIMIT:
            _CACHE_ENTRIES.popitem(last=False)
        return copy.deepcopy(payload)


def _quoted_table(table: str) -> str:
    # Tables originate from a strict six-digit A-prefixed allowlist.
    return f'"{table}"'


def _parse_int_query(name: str, *, default: int, minimum: int, maximum: int) -> int:
    if len(request.args.getlist(name)) > 1:
        raise ValueError
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        return max(minimum, min(maximum, int(raw)))
    except ValueError as exc:
        raise ValueError from exc


def _symbol_query() -> tuple[str, int]:
    if set(request.args) - {"code", "max_points"}:
        raise ValueError
    if len(request.args.getlist("code")) != 1 or len(request.args.getlist("max_points")) > 1:
        raise ValueError
    code = request.args.get("code", "")
    if not CODE_PATTERN.fullmatch(code):
        raise ValueError
    raw = request.args.get("max_points")
    if raw is None:
        return code, 1500
    try:
        return code, max(100, min(4000, int(raw)))
    except ValueError as exc:
        raise ValueError from exc


def _blocked_database() -> dict[str, Any]:
    return {"status": "BLOCKED", "reason": "DAILY_DATABASE_UNAVAILABLE"}


def _symbol_payload(code: str, max_points: int) -> dict[str, Any]:
    table = f"A{code}"
    try:
        with _connect() as connection:
            rows = connection.execute(
                f"SELECT date, close, volume, 외국인현보유비율, 기관순매수 FROM {_quoted_table(table)} ORDER BY date"
            ).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            return {"status": "BLOCKED", "reason": "SYMBOL_TABLE_MISSING"}
        return _blocked_database()
    except (OSError, sqlite3.Error):
        return _blocked_database()

    total_rows = len(rows)
    sampled = total_rows > max_points
    stride: int | None = None
    if sampled:
        stride = max(1, math.ceil((total_rows - 1) / (max_points - 1)))
        sampled_rows = rows[::stride]
        if sampled_rows[-1][0] != rows[-1][0]:
            sampled_rows.append(rows[-1])
        rows = sampled_rows
    series = [
        {"date": row[0], "close": row[1], "volume": row[2], "foreign_ratio": row[3], "inst_netbuy": row[4]}
        for row in rows
    ]
    return {
        "schema_version": "kronos_v6_insight_symbol.v1",
        "status": "OK",
        "code": code,
        "table": table,
        "total_rows": total_rows,
        "sampled": sampled,
        "stride": stride,
        "series": series,
        "price_basis_caveat": PRICE_BASIS_CAVEAT,
        "flow_caveat": FLOW_CAVEAT,
    }


def _flow_record(connection: sqlite3.Connection, table: str, window: int) -> dict[str, Any] | None:
    try:
        rows = connection.execute(
            f"SELECT date, close, 외국인현보유비율, 기관순매수 FROM {_quoted_table(table)} ORDER BY date DESC LIMIT ?",
            (window,),
        ).fetchall()
    except sqlite3.Error:
        return None
    if not rows:
        return None
    rows.reverse()
    foreign_values = [row[2] for row in rows]
    inst_values = [row[3] for row in rows]
    return {
        "table": table,
        "code": table[1:],
        "inst_netbuy_sum": sum(value for value in inst_values if value is not None) if any(value is not None for value in inst_values) else None,
        "foreign_ratio_delta": (foreign_values[-1] - foreign_values[0]) if foreign_values[0] is not None and foreign_values[-1] is not None else None,
        "last_close": rows[-1][1],
        "last_date": rows[-1][0],
    }


def _rank(records: list[dict[str, Any]], field: str, descending: bool, limit: int) -> list[dict[str, Any]]:
    def key(record: dict[str, Any]) -> tuple[bool, float, str]:
        value = record[field]
        return value is None, (-float(value) if descending and value is not None else float(value or 0)), record["table"]
    return sorted(records, key=key)[:limit]


def _flow_payload(window: int, limit: int) -> dict[str, Any]:
    for _ in range(2):
        tables, revision = _cache_snapshot()
        _cache_activate(revision)
        if tables is None:
            return {"status": "BLOCKED", "reason": "UNIVERSE_MANIFEST_MISSING"}
        if revision[1][0] is None:
            return _blocked_database()
        key = ("flow", window, limit)
        cached = _cache_get(revision, key)
        if cached is not None:
            return cached
        try:
            with _connect() as connection:
                records = [record for table in tables if (record := _flow_record(connection, table, window)) is not None]
        except sqlite3.Error:
            return _blocked_database()
        payload = {
            "schema_version": "kronos_v6_insight_flow.v1",
            "status": "OK",
            "window": window,
            "limit": limit,
            "top_inst_buy": _rank(records, "inst_netbuy_sum", True, limit),
            "top_inst_sell": _rank(records, "inst_netbuy_sum", False, limit),
            "top_foreign_gain": _rank(records, "foreign_ratio_delta", True, limit),
            "top_foreign_loss": _rank(records, "foreign_ratio_delta", False, limit),
            "price_basis_caveat": PRICE_BASIS_CAVEAT,
            "flow_caveat": FLOW_CAVEAT,
            "not_a_recommendation": True,
            "note": "연구 관측용 순위이며 매수 추천이 아닙니다",
        }
        if _cache_snapshot()[1] != revision:
            continue
        cached = _cache_store(revision, key, payload)
        if cached is not None:
            return cached
    return copy.deepcopy(payload)


def _index_regime() -> dict[str, Any]:
    """Derive a read-only index observation from validated offline artifacts."""
    try:
        from webui.v6_platform_api import INDEX_MARKETS, index_overlay_series
    except ImportError:
        return dict(INDEX_BLOCKER_REGIME)
    series_by_market = index_overlay_series()
    if not all(market in series_by_market for market in INDEX_MARKETS):
        return dict(INDEX_BLOCKER_REGIME)
    markets: dict[str, Any] = {}
    for market, rows in sorted(series_by_market.items()):
        if not rows:
            return dict(INDEX_BLOCKER_REGIME)
        closes = [float(row["close"]) for row in rows[-20:]]
        mean20 = sum(closes) / len(closes)
        last = rows[-1]
        markets[market] = {
            "last_date": last["date"],
            "last_close": float(last["close"]),
            "pct_vs_20d_mean": ((float(last["close"]) / mean20) - 1.0) * 100.0 if mean20 else None,
            "window_days": len(closes),
        }
    return {
        "state": "PRESENT",
        "markets": markets,
        "caveat": "pykrx offline artifact index levels only; observation only, not a trading signal",
    }


def _regime_payload() -> dict[str, Any]:
    index_regime = _index_regime()
    for _ in range(2):
        tables, revision = _cache_snapshot()
        _cache_activate(revision)
        if tables is None:
            return {"index_regime": index_regime, "breadth_proxy": {"status": "BLOCKED", "reason": "UNIVERSE_MANIFEST_MISSING"}}
        if revision[1][0] is None:
            return {"index_regime": index_regime, "breadth_proxy": {"status": "BLOCKED", "reason": "DAILY_DATABASE_UNAVAILABLE"}}
        key = ("regime", 0, 0)
        cached = _cache_get(revision, key)
        if cached is not None:
            return {"index_regime": index_regime, "breadth_proxy": cached}
        sampled_tables = tables[:200]
        try:
            with _connect() as connection:
                maxima: list[Any] = []
                for table in sampled_tables:
                    maximum = connection.execute(f"SELECT MAX(date) FROM {_quoted_table(table)}").fetchone()[0]
                    if maximum is not None:
                        maxima.append(maximum)
                as_of_date = min(maxima) if maxima else None
                evaluated = 0
                above = 0
                if as_of_date is not None:
                    for table in sampled_tables:
                        rows = connection.execute(
                            f"SELECT close FROM {_quoted_table(table)} WHERE date <= ? ORDER BY date DESC LIMIT 20",
                            (as_of_date,),
                        ).fetchall()
                        if not rows or rows[0][0] is None or any(row[0] is None for row in rows):
                            continue
                        evaluated += 1
                        if rows[0][0] > sum(row[0] for row in rows) / len(rows):
                            above += 1
        except sqlite3.Error:
            return {"index_regime": index_regime, "breadth_proxy": {"status": "BLOCKED", "reason": "DAILY_DATABASE_UNAVAILABLE"}}
        breadth = {
            "as_of_date": as_of_date,
            "tables_evaluated": evaluated,
            "pct_above_20s_mean": (above / evaluated * 100) if evaluated else None,
            "disclaimer": "universe breadth proxy from daily DB; NOT an index regime; price basis unverified",
        }
        if _cache_snapshot()[1] != revision:
            continue
        cached = _cache_store(revision, key, breadth)
        if cached is not None:
            return {"index_regime": index_regime, "breadth_proxy": cached}
    return {"index_regime": index_regime, "breadth_proxy": copy.deepcopy(breadth)}


def create_v6_insight_blueprint(*, name: str = "v6_insight", url_prefix: str = "/api/v6/insight") -> Blueprint:
    """Create the V6 GET-only insight API blueprint."""
    blueprint = Blueprint(name, __name__, url_prefix=url_prefix)

    def symbol_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        try:
            code, max_points = _symbol_query()
        except ValueError:
            return _error(400, "BAD_REQUEST")
        return _response(_symbol_payload(code, max_points))

    def flow_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        try:
            window = _parse_int_query("window", default=20, minimum=5, maximum=120)
            limit = _parse_int_query("limit", default=30, minimum=5, maximum=100)
        except ValueError:
            return _error(400, "BAD_REQUEST")
        if set(request.args) - {"window", "limit"} or any(len(request.args.getlist(name)) > 1 for name in ("window", "limit")):
            return _error(400, "BAD_REQUEST")
        return _response(_flow_payload(window, limit))

    def regime_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed()
        if request.args:
            return _error(400, "BAD_REQUEST")
        return _response(_regime_payload())

    for rule, endpoint, handler in (("/symbol", "symbol", symbol_handler), ("/flow", "flow", flow_handler), ("/regime", "regime", regime_handler)):
        blueprint.add_url_rule(rule, endpoint=endpoint, view_func=handler, methods=list(ALL_ROUTE_METHODS), provide_automatic_options=False)
    return blueprint


create_blueprint = create_v6_insight_blueprint

__all__ = [
    "DAILY_DB_PATH",
    "UNIVERSE_MANIFEST_PATH",
    "create_blueprint",
    "create_v6_insight_blueprint",
    "reset_v6_insight_cache",
    "v6_insight_cache_stats",
]
