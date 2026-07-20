"""Read-only V6 daily-data insight API for research observation."""
from __future__ import annotations

import json
import math
import re
import sqlite3
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
_FLOW_CACHE: dict[tuple[int, int, int], dict[str, Any]] = {}
_REGIME_CACHE: dict[tuple[int], dict[str, Any]] = {}
INDEX_BLOCKER_REGIME: Final = {"state": "BLOCKED_INDEX_SERIES_SOURCE", "reason": "KRX credentials required for pykrx collection"}


def _response(payload: Mapping[str, Any], status_code: int = 200) -> Response:
    return Response(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), status=status_code, mimetype="application/json")


def _error(status_code: int, code: str) -> Response:
    return _response({"status": "ERROR", "error": {"code": code}}, status_code)


def _method_not_allowed() -> Response:
    response = _error(405, "METHOD_NOT_ALLOWED")
    response.headers["Allow"] = "GET"
    return response


def _database_mtime() -> int | None:
    try:
        return DAILY_DB_PATH.stat().st_mtime_ns
    except OSError:
        return None


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(f"{DAILY_DB_PATH.resolve().as_uri()}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only = ON")
    return connection


def _manifest_tables() -> list[str] | None:
    try:
        value = json.loads(UNIVERSE_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(value, Mapping) or not isinstance(value.get("universe"), list):
        return None
    tables: list[str] = []
    for item in value["universe"]:
        table = item.get("table") if isinstance(item, Mapping) else None
        if isinstance(table, str) and TABLE_PATTERN.fullmatch(table):
            tables.append(table)
    return tables


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
    tables = _manifest_tables()
    if tables is None:
        return {"status": "BLOCKED", "reason": "UNIVERSE_MANIFEST_MISSING"}
    mtime = _database_mtime()
    if mtime is None:
        return _blocked_database()
    key = (window, limit, mtime)
    if key in _FLOW_CACHE:
        return _FLOW_CACHE[key]
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
    _FLOW_CACHE[key] = payload
    return payload


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
    tables = _manifest_tables()
    index_regime = _index_regime()
    if tables is None:
        return {"index_regime": index_regime, "breadth_proxy": {"status": "BLOCKED", "reason": "UNIVERSE_MANIFEST_MISSING"}}
    mtime = _database_mtime()
    if mtime is None:
        return {"index_regime": index_regime, "breadth_proxy": {"status": "BLOCKED", "reason": "DAILY_DATABASE_UNAVAILABLE"}}
    key = (mtime,)
    if key in _REGIME_CACHE:
        return {"index_regime": index_regime, "breadth_proxy": _REGIME_CACHE[key]}
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
    _REGIME_CACHE[key] = breadth
    return {"index_regime": index_regime, "breadth_proxy": breadth}


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

__all__ = ["DAILY_DB_PATH", "UNIVERSE_MANIFEST_PATH", "create_blueprint", "create_v6_insight_blueprint"]
