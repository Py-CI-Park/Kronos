"""Reprice frozen gap-up instance manifests under alternate fill modes.

This is a research artifact generator for the probability-lane factory.  It does
not discover a new entry universe: the input manifest fixes the symbol/session
set and the output only recomputes TP/SL outcomes under a requested fill model.
The resulting artifacts remain generated evidence, not live-trading readiness.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from stom_rl.gap_up_backtest import (
    COST_BPS_ROUND_TRIP,
    ENTRY_FILTERS,
    GapUpBacktestConfig,
    SESSION_START_HHMMSS,
    TIME_EXIT_HHMMSS,
    PROJECT_ROOT,
    GapUpInstance,
    _CHANGE_RATE_CANDIDATES,
    _PRICE_CANDIDATES,
    _SEC_AMOUNT_CANDIDATES,
    _TIMESTAMP_CANDIDATES,
    _TRADE_STRENGTH_CANDIDATES,
    _BID_QTY_CANDIDATES,
    _ASK_QTY_CANDIDATES,
    _quote_ident,
    _resolve_column,
    _seconds_since_midnight,
    connect_readonly,
    compute_bid_ask_imbalance,
    get_table_columns,
    passes_entry_filter,
    simulate_baseline,
    simulate_trade,
)

FILL_MODES = ("idealized", "realized", "sl_gap_stress")
DEFAULT_BASE_INSTANCES = Path(".omx") / "artifacts" / "gap_up_full" / "instances.json"
DEFAULT_BASE_SUMMARY = Path(".omx") / "artifacts" / "gap_up_full" / "summary.json"
DEFAULT_DB = str(PROJECT_ROOT / "_database" / "stock_tick_back.db")


class FillModeInstanceError(RuntimeError):
    """Raised when a frozen manifest cannot be repriced honestly."""


@dataclass(frozen=True, slots=True)
class RepriceConfig:
    base_instances: Path = DEFAULT_BASE_INSTANCES
    base_summary: Path = DEFAULT_BASE_SUMMARY
    output_dir: Path = Path(".omx") / "artifacts" / "gap_up_repriced"
    db_path: str = DEFAULT_DB
    fill_mode: str = "realized"
    cost_bps: float = COST_BPS_ROUND_TRIP
    strict: bool = True


def _load_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise FillModeInstanceError(f"base instances must be a non-empty list: {path}")
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(payload):
        if not isinstance(row, dict):
            raise FillModeInstanceError(f"base row {idx} is not an object")
        symbol = str(row.get("symbol", ""))
        session = str(row.get("session", ""))
        if not symbol or len(session) != 8 or not session.isdigit():
            raise FillModeInstanceError(f"base row {idx} lacks a valid symbol/session")
        rows.append(dict(row))
    return rows


def _load_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _resolve_table_columns(conn: Any, table: str) -> dict[str, str | None]:
    columns = get_table_columns(conn, table)
    resolved = {
        "timestamp_col": _resolve_column(columns, _TIMESTAMP_CANDIDATES),
        "price_col": _resolve_column(columns, _PRICE_CANDIDATES),
        "change_rate_col": _resolve_column(columns, _CHANGE_RATE_CANDIDATES),
        "trade_strength_col": _resolve_column(columns, _TRADE_STRENGTH_CANDIDATES),
        "sec_amount_col": _resolve_column(columns, _SEC_AMOUNT_CANDIDATES),
        "bid_qty_col": _resolve_column(columns, _BID_QTY_CANDIDATES),
        "ask_qty_col": _resolve_column(columns, _ASK_QTY_CANDIDATES),
    }
    if not resolved["timestamp_col"] or not resolved["price_col"] or not resolved["change_rate_col"]:
        raise FillModeInstanceError(f"table lacks required columns: {table}")
    return resolved


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _chunks(values: Sequence[str], size: int = 400) -> Sequence[Sequence[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def _instance_from_rows(
    table: str,
    session: str,
    rows: Sequence[Sequence[Any]],
    *,
    entry_threshold: float,
) -> GapUpInstance | None:
    if not rows:
        return None
    entry_row = rows[0]
    entry_px = _opt_float(entry_row[1])
    entry_cr = _opt_float(entry_row[2])
    if entry_px is None or entry_cr is None or entry_px <= 0 or entry_cr < entry_threshold:
        return None

    entry_trade_strength = _opt_float(entry_row[3])
    entry_sec_amount = _opt_float(entry_row[4])
    entry_bid_qty = _opt_float(entry_row[5])
    entry_ask_qty = _opt_float(entry_row[6])
    entry_imbalance = compute_bid_ask_imbalance(entry_bid_qty, entry_ask_qty)

    prices: list[float] = []
    secs: list[int] = []
    for row in rows:
        px = _opt_float(row[1])
        if px is None or px <= 0:
            continue
        prices.append(px)
        secs.append(_seconds_since_midnight(int(row[0])))
    if not prices:
        return None
    return GapUpInstance(
        symbol=str(table),
        session=str(session),
        entry_change_rate=float(entry_cr),
        entry_price=prices[0],
        prices=tuple(prices),
        seconds=tuple(secs),
        entry_trade_strength=entry_trade_strength,
        entry_sec_amount=entry_sec_amount,
        entry_bid_ask_imbalance=entry_imbalance,
    )


def _read_instances_for_sessions(
    conn: Any,
    table: str,
    sessions: Sequence[str],
    cols: Mapping[str, str | None],
    *,
    entry_threshold: float,
) -> dict[str, GapUpInstance]:
    qt = _quote_ident(table)
    ts_q = _quote_ident(str(cols["timestamp_col"]))
    px_q = _quote_ident(str(cols["price_col"]))
    cr_q = _quote_ident(str(cols["change_rate_col"]))
    extra_cols = [
        cols.get("trade_strength_col"),
        cols.get("sec_amount_col"),
        cols.get("bid_qty_col"),
        cols.get("ask_qty_col"),
    ]
    select_extra = "".join(f", {_quote_ident(str(c))}" if c else ", NULL" for c in extra_cols)
    out: dict[str, GapUpInstance] = {}
    ordered_sessions = sorted({str(s) for s in sessions})
    for chunk in _chunks(ordered_sessions):
        placeholders = ",".join("?" for _ in chunk)
        query = (
            f"SELECT {ts_q}, {px_q}, {cr_q}{select_extra} FROM {qt} "
            f"WHERE substr(CAST({ts_q} AS TEXT), 1, 8) IN ({placeholders}) "
            f"AND substr(CAST({ts_q} AS TEXT), 9, 6) >= ? "
            f"AND substr(CAST({ts_q} AS TEXT), 9, 6) <= ? "
            f"ORDER BY {ts_q}"
        )
        params = [*chunk, SESSION_START_HHMMSS, TIME_EXIT_HHMMSS]
        grouped: dict[str, list[Sequence[Any]]] = {str(session): [] for session in chunk}
        for row in conn.execute(query, params).fetchall():
            session = str(int(row[0]))[:8]
            if session in grouped:
                grouped[session].append(row)
        for session, rows in grouped.items():
            inst = _instance_from_rows(
                table,
                session,
                rows,
                entry_threshold=entry_threshold,
            )
            if inst is not None:
                out[session] = inst
    return out


def build_repriced_row(
    base_row: Mapping[str, Any],
    inst: GapUpInstance,
    *,
    config: GapUpBacktestConfig,
    fill_mode: str,
    cost_bps: float,
) -> dict[str, Any]:
    """Return one manifest row with outcomes recomputed for ``fill_mode``."""

    rec: dict[str, Any] = dict(base_row)
    rec.update(
        {
            "symbol": str(inst.symbol),
            "session": str(inst.session),
            "entry_change_rate": inst.entry_change_rate,
            "entry_price": inst.entry_price,
            "entry_trade_strength": inst.entry_trade_strength,
            "entry_sec_amount": inst.entry_sec_amount,
            "entry_bid_ask_imbalance": (
                round(inst.entry_bid_ask_imbalance, 6)
                if inst.entry_bid_ask_imbalance is not None
                else None
            ),
            "pass_ts": passes_entry_filter(inst, ENTRY_FILTERS["ts"]),
            "pass_ts_imb": passes_entry_filter(inst, ENTRY_FILTERS["ts_imb"]),
            "n_path_bars": len(inst.prices),
            "fill_mode": fill_mode,
            "source_cost_bps": cost_bps,
        }
    )
    for tp in config.tp_grid:
        for sl in config.sl_grid:
            tr = simulate_trade(
                inst.prices,
                tp_pct=tp,
                sl_pct=sl,
                cost_bps=cost_bps,
                seconds=inst.seconds,
                fill_mode=fill_mode,
            )
            key = f"tp{tp:g}_sl{sl:g}"
            rec[f"{key}_reason"] = tr.exit_reason
            rec[f"{key}_net_pct"] = round(tr.net_return_pct, 6)
    base = simulate_baseline(inst.prices, cost_bps=cost_bps, seconds=inst.seconds)
    rec["baseline_net_pct"] = round(base.net_return_pct, 6)
    rec["baseline_hold_seconds"] = base.hold_seconds
    return rec


def reprice_instances(config: RepriceConfig) -> dict[str, Any]:
    """Recompute a frozen symbol/session manifest under one fill mode."""

    if config.fill_mode not in FILL_MODES:
        raise FillModeInstanceError(f"fill_mode must be one of {FILL_MODES!r}")
    base_rows = _load_rows(config.base_instances)
    base_summary = _load_summary(config.base_summary)
    backtest_config = GapUpBacktestConfig(db_path=config.db_path, cost_bps=config.cost_bps)
    out_rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    instances_by_key: dict[tuple[str, str], GapUpInstance] = {}
    errors_by_key: dict[tuple[str, str], str] = {}
    rows_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for row in base_rows:
        rows_by_symbol.setdefault(str(row["symbol"]), []).append(row)

    conn = connect_readonly(config.db_path)
    try:
        for symbol, symbol_rows in sorted(rows_by_symbol.items()):
            sessions = [str(row["session"]) for row in symbol_rows]
            try:
                cols = _resolve_table_columns(conn, symbol)
                found = _read_instances_for_sessions(
                    conn,
                    symbol,
                    sessions,
                    cols,
                    entry_threshold=backtest_config.entry_threshold,
                )
            except Exception as exc:  # noqa: BLE001 - surfaced in strict mode below
                for session in sessions:
                    errors_by_key[(symbol, session)] = str(exc)
                continue
            for session in sessions:
                inst = found.get(session)
                if inst is None:
                    errors_by_key[(symbol, session)] = "not_found_or_below_threshold"
                else:
                    instances_by_key[(symbol, session)] = inst
    finally:
        conn.close()

    for row in base_rows:
        symbol = str(row["symbol"])
        session = str(row["session"])
        inst = instances_by_key.get((symbol, session))
        if inst is None:
            missing.append(
                {
                    "symbol": symbol,
                    "session": session,
                    "reason": errors_by_key.get((symbol, session), "not_found_or_below_threshold"),
                }
            )
            continue
        out_rows.append(
            build_repriced_row(
                row,
                inst,
                config=backtest_config,
                fill_mode=config.fill_mode,
                cost_bps=config.cost_bps,
            )
        )

    if missing and config.strict:
        sample = missing[:3]
        raise FillModeInstanceError(
            f"{len(missing)} base instances could not be repriced; sample={sample!r}"
        )

    sessions = sorted({str(row["session"]) for row in out_rows})
    summary = {
        "artifact_type": "repriced_gap_up_instances",
        "source_instances_path": str(config.base_instances),
        "source_summary_path": str(config.base_summary),
        "source_n_instances": len(base_rows),
        "n_instances": len(out_rows),
        "n_missing": len(missing),
        "missing_sample": missing[:20],
        "n_symbols": len({str(row["symbol"]) for row in out_rows}),
        "n_sessions": len({(str(row["symbol"]), str(row["session"])) for row in out_rows}),
        "date_min": min(sessions) if sessions else None,
        "date_max": max(sessions) if sessions else None,
        "boundary_date": base_summary.get("boundary_date"),
        "cost_bps": config.cost_bps,
        "fill_mode": config.fill_mode,
        "entry_threshold": backtest_config.entry_threshold,
        "tp_grid": list(backtest_config.tp_grid),
        "sl_grid": list(backtest_config.sl_grid),
        "primary_tp_pct": backtest_config.primary_tp_pct,
        "primary_sl_pct": backtest_config.primary_sl_pct,
        "guardrail": (
            "Frozen gap-up manifest repriced under alternate fill mode; generated "
            "research artifact only, no profit/live-readiness claim."
        ),
    }

    config.output_dir.mkdir(parents=True, exist_ok=True)
    (config.output_dir / "instances.json").write_text(
        json.dumps(out_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (config.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {**summary, "output_dir": str(config.output_dir)}


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-instances", default=str(DEFAULT_BASE_INSTANCES))
    parser.add_argument("--base-summary", default=str(DEFAULT_BASE_SUMMARY))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--fill-mode", choices=FILL_MODES, required=True)
    parser.add_argument("--cost-bps", type=float, default=COST_BPS_ROUND_TRIP)
    parser.add_argument("--allow-missing", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = reprice_instances(
        RepriceConfig(
            base_instances=Path(args.base_instances),
            base_summary=Path(args.base_summary),
            output_dir=Path(args.output_dir),
            db_path=str(args.db),
            fill_mode=str(args.fill_mode),
            cost_bps=float(args.cost_bps),
            strict=not bool(args.allow_missing),
        )
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
