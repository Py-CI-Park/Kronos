"""Opening gap-up momentum backtest (시초 갭상승 전략) on the real 1-second DB.

Strategy (user-specified, pre-registered BEFORE reading any result)
-------------------------------------------------------------------
* **Entry (시초 갭상승)** — for each recorded ``(symbol, session)`` in
  ``_database/stock_tick_back.db`` look at the FIRST bar of the session
  (the earliest row at or after ``09:00:00``).  If that bar's ``등락율``
  (percent change vs. previous close, stored in the DB) is ``>= 2.0`` enter
  LONG at that bar's ``현재가`` (current price).
* **Exit (first to trigger)** — walk the intra-session 1-second ``현재가``
  path FORWARD from the entry bar:
    - take-profit when price ``>= entry * (1 + tp_pct/100)``;
    - stop-loss when price ``<= entry * (1 - sl_pct/100)``;
    - else time-exit at ``09:25:00`` (시간청산) at that bar's price.
  The forward walk IS the legitimate trade execution — it only consumes
  prices at or after the entry second, so there is NO look-ahead at ENTRY
  (the entry decision uses only the first bar's 등락율).
* **Cost** — 25 bps round-trip (entry + exit combined) deducted from each
  trade's gross return.

Honesty caveats (locked, see the doc)
-------------------------------------
* The TP/SL pair is SWEPT over a small grid (``TP x SL``); the full surface
  is reported and no single cell is cherry-picked as "the" answer.
* The universe is a TRIGGERED subset: the DB only recorded a session because
  it hit *some* STOM condition, so 등락율>=2% instances here are NOT a random
  sample of all 2%+ market gap-ups.  Results may not generalise.
* In-sample / out-of-sample split is by DATE (earlier sessions in-sample,
  later sessions out-of-sample) so an overfit TP/SL is exposed.

Bounded reads (NO full 28GB scan)
---------------------------------
Sessions are enumerated with the cheap per-table
``SELECT DISTINCT substr(index,1,8)`` query (:func:`enumerate_sessions`,
Story B1 pattern), then each ``(symbol, session)`` is read with a single
session-prefix-filtered, index-ordered query over the entry->09:25 window.
Each per-instance read touches one table's morning window only.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from finetune_csv.stom_tick_dataset import (  # noqa: E402
    connect_readonly,
    get_table_columns,
    list_stock_tables,
)

# ---------------------------------------------------------------------------
# Locked pre-registration constants (DO NOT tune after seeing results).
# ---------------------------------------------------------------------------
ENTRY_CHANGE_RATE_THRESHOLD: float = 2.0  # 등락율 >= 2.0% at the first bar
TIME_EXIT_HHMMSS: str = "092500"  # 시간청산 cutoff (data ends ~0930)
SESSION_START_HHMMSS: str = "090000"
COST_BPS_ROUND_TRIP: float = 25.0  # entry + exit combined, basis points

# Swept TP/SL grid (M = 16 combos).  Reported in full; no cherry-pick.
TP_GRID_PCT: Tuple[float, ...] = (1.0, 2.0, 3.0, 5.0)
SL_GRID_PCT: Tuple[float, ...] = (1.0, 1.5, 2.0, 3.0)

# DB column resolution (Korean names stored UTF-8; sqlite3 decodes by default).
_TIMESTAMP_CANDIDATES: Tuple[str, ...] = ("index", "timestamps", "timestamp")
_PRICE_CANDIDATES: Tuple[str, ...] = ("현재가", "종가", "close")
_CHANGE_RATE_CANDIDATES: Tuple[str, ...] = ("등락율",)

# Exit-reason labels.
EXIT_TP = "tp"
EXIT_SL = "sl"
EXIT_TIME = "time"


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _resolve_column(columns: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    column_set = set(columns)
    for candidate in candidates:
        if candidate in column_set:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Pure trade-execution core (unit-tested on synthetic paths; no DB / no I/O).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TradeResult:
    """One resolved gap-up trade.

    ``net_return_pct`` is the round-trip-cost-adjusted percent return; the gross
    return is the raw exit/entry move.  ``exit_reason`` is one of
    :data:`EXIT_TP` / :data:`EXIT_SL` / :data:`EXIT_TIME`.
    """

    entry_price: float
    exit_price: float
    exit_reason: str
    hold_seconds: int
    gross_return_pct: float
    net_return_pct: float


def simulate_trade(
    prices: Sequence[float],
    *,
    tp_pct: float,
    sl_pct: float,
    cost_bps: float = COST_BPS_ROUND_TRIP,
    seconds: Optional[Sequence[int]] = None,
) -> TradeResult:
    """Walk a forward 1s price path from entry and resolve the exit.

    ``prices[0]`` is the entry (the first bar's price); subsequent elements are
    the forward path up to and including the time-exit bar (the caller bounds
    the path at 09:25:00).  The walk returns at the FIRST second whose price
    crosses TP or SL; if neither triggers it time-exits at the last price.

    A bar that crosses BOTH the TP and SL thresholds in the same second
    (a gap through the band) is resolved CONSERVATIVELY as a stop-loss — the
    pessimistic assumption for a long, since we cannot know intra-second order.

    ``net_return_pct`` subtracts the full round-trip ``cost_bps`` (entry+exit)
    from the gross move.  ``seconds`` (optional) supplies the elapsed-second of
    each path element so the reported ``hold_seconds`` reflects wall-clock time;
    when absent the index is used.
    """

    if tp_pct <= 0 or sl_pct <= 0:
        raise ValueError("tp_pct and sl_pct must be positive")
    if not prices:
        raise ValueError("prices must contain at least the entry bar")
    entry = float(prices[0])
    if entry <= 0:
        raise ValueError("entry price must be positive")

    tp_level = entry * (1.0 + tp_pct / 100.0)
    sl_level = entry * (1.0 - sl_pct / 100.0)
    cost_pct = float(cost_bps) / 100.0  # 25 bps -> 0.25%

    def _elapsed(idx: int) -> int:
        if seconds is not None and idx < len(seconds):
            return int(seconds[idx]) - int(seconds[0])
        return int(idx)

    exit_idx = len(prices) - 1
    exit_price = float(prices[-1])
    exit_reason = EXIT_TIME

    # Forward walk: start at the SECOND bar (index 1).  The entry bar itself
    # cannot also be the exit — the trade is opened on it.
    for idx in range(1, len(prices)):
        price = float(prices[idx])
        hit_sl = price <= sl_level
        hit_tp = price >= tp_level
        if hit_sl:  # conservative: SL wins a same-bar TP+SL straddle
            exit_idx, exit_price, exit_reason = idx, sl_level, EXIT_SL
            break
        if hit_tp:
            exit_idx, exit_price, exit_reason = idx, tp_level, EXIT_TP
            break

    gross = (exit_price / entry - 1.0) * 100.0
    net = gross - cost_pct
    return TradeResult(
        entry_price=entry,
        exit_price=float(exit_price),
        exit_reason=exit_reason,
        hold_seconds=_elapsed(exit_idx),
        gross_return_pct=float(gross),
        net_return_pct=float(net),
    )


def simulate_baseline(
    prices: Sequence[float],
    *,
    cost_bps: float = COST_BPS_ROUND_TRIP,
    seconds: Optional[Sequence[int]] = None,
) -> TradeResult:
    """Baseline: buy@open, hold to the time-exit bar, NO TP/SL.

    Exit is always the last price on the bounded path (09:25), so this measures
    "just ride the gap" net of the same round-trip cost.
    """

    if not prices:
        raise ValueError("prices must contain at least the entry bar")
    entry = float(prices[0])
    if entry <= 0:
        raise ValueError("entry price must be positive")
    exit_price = float(prices[-1])
    cost_pct = float(cost_bps) / 100.0
    gross = (exit_price / entry - 1.0) * 100.0
    net = gross - cost_pct
    last_idx = len(prices) - 1
    if seconds is not None and last_idx < len(seconds):
        hold = int(seconds[last_idx]) - int(seconds[0])
    else:
        hold = int(last_idx)
    return TradeResult(
        entry_price=entry,
        exit_price=exit_price,
        exit_reason=EXIT_TIME,
        hold_seconds=hold,
        gross_return_pct=float(gross),
        net_return_pct=float(net),
    )


# ---------------------------------------------------------------------------
# Per-instance DB read (bounded; session-prefix indexed; entry->09:25 window).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GapUpInstance:
    """A resolved gap-up entry candidate for one (symbol, session)."""

    symbol: str
    session: str
    entry_change_rate: float
    entry_price: float
    prices: Tuple[float, ...]
    seconds: Tuple[int, ...]


def _hhmmss_of(ts: int) -> str:
    return str(int(ts))[8:14]


def _seconds_since_midnight(ts: int) -> int:
    s = str(int(ts))
    hh, mm, ss = int(s[8:10]), int(s[10:12]), int(s[12:14])
    return hh * 3600 + mm * 60 + ss


def read_gap_up_instance(
    conn: Any,
    table: str,
    session: str,
    *,
    timestamp_col: str,
    price_col: str,
    change_rate_col: str,
    entry_threshold: float = ENTRY_CHANGE_RATE_THRESHOLD,
    session_start: str = SESSION_START_HHMMSS,
    time_exit: str = TIME_EXIT_HHMMSS,
) -> Optional[GapUpInstance]:
    """Read one (symbol, session) window and return a gap-up instance or None.

    A single session-prefix-filtered, index-ordered query pulls the rows from
    ``session_start`` to ``time_exit`` (inclusive).  The entry is the FIRST row;
    if its 등락율 < ``entry_threshold`` (or price is non-positive) the session is
    skipped (returns None).  The forward path is every row from entry to the
    time-exit cutoff.  This touches one table's morning window only.
    """

    if len(session) != 8 or not session.isdigit():
        raise ValueError(f"session must be YYYYMMDD, got: {session}")
    qt = _quote_ident(table)
    ts_q = _quote_ident(timestamp_col)
    px_q = _quote_ident(price_col)
    cr_q = _quote_ident(change_rate_col)
    start_full = int(session + session_start)
    end_full = int(session + time_exit)
    query = (
        f"SELECT {ts_q}, {px_q}, {cr_q} FROM {qt} "
        f"WHERE {ts_q} >= ? AND {ts_q} <= ? "
        f"ORDER BY {ts_q}"
    )
    rows = conn.execute(query, (start_full, end_full)).fetchall()
    if not rows:
        return None

    # Entry = first bar of the session window.
    entry_ts, entry_px, entry_cr = rows[0]
    if entry_cr is None or entry_px is None:
        return None
    try:
        entry_cr = float(entry_cr)
        entry_px = float(entry_px)
    except (TypeError, ValueError):
        return None
    if entry_px <= 0 or entry_cr < float(entry_threshold):
        return None

    prices: List[float] = []
    secs: List[int] = []
    for ts, px, _cr in rows:
        if px is None:
            continue
        try:
            p = float(px)
        except (TypeError, ValueError):
            continue
        if p <= 0:
            continue
        prices.append(p)
        secs.append(_seconds_since_midnight(int(ts)))
    if len(prices) < 1:
        return None

    return GapUpInstance(
        symbol=str(table),
        session=str(session),
        entry_change_rate=entry_cr,
        entry_price=prices[0],
        prices=tuple(prices),
        seconds=tuple(secs),
    )


# ---------------------------------------------------------------------------
# Aggregation over a set of resolved trades.
# ---------------------------------------------------------------------------
def aggregate_trades(trades: Sequence[TradeResult]) -> Dict[str, Any]:
    """Summarise a set of resolved trades into honest aggregate metrics."""

    n = len(trades)
    if n == 0:
        return {
            "n_trades": 0,
            "win_rate": None,
            "mean_net_return_pct": None,
            "total_net_return_pct": 0.0,
            "expectancy_pct": None,
            "mean_gross_return_pct": None,
            "avg_hold_seconds": None,
            "exit_mix": {EXIT_TP: 0.0, EXIT_SL: 0.0, EXIT_TIME: 0.0},
        }
    nets = [t.net_return_pct for t in trades]
    grosses = [t.gross_return_pct for t in trades]
    holds = [t.hold_seconds for t in trades]
    wins = sum(1 for v in nets if v > 0.0)
    counts = {EXIT_TP: 0, EXIT_SL: 0, EXIT_TIME: 0}
    for t in trades:
        counts[t.exit_reason] = counts.get(t.exit_reason, 0) + 1
    total_net = float(sum(nets))
    return {
        "n_trades": n,
        "win_rate": wins / n,
        "mean_net_return_pct": total_net / n,
        "total_net_return_pct": total_net,
        "expectancy_pct": total_net / n,  # per-trade expectancy net of cost
        "mean_gross_return_pct": float(sum(grosses)) / n,
        "avg_hold_seconds": float(sum(holds)) / n,
        "exit_mix": {k: counts[k] / n for k in (EXIT_TP, EXIT_SL, EXIT_TIME)},
    }


def split_instances_by_date(
    instances: Sequence[GapUpInstance],
    in_sample_fraction: float = 0.7,
) -> Tuple[List[GapUpInstance], List[GapUpInstance], Optional[str]]:
    """Split instances by SESSION DATE into in-sample (earlier) / OOS (later).

    The split boundary is the date at the ``in_sample_fraction`` quantile of the
    sorted distinct session dates.  All instances on a date <= boundary are
    in-sample; later dates are out-of-sample.  Returns
    ``(in_sample, out_of_sample, boundary_date)``.
    """

    if not instances:
        return [], [], None
    dates = sorted({inst.session for inst in instances})
    if len(dates) == 1:
        return list(instances), [], dates[0]
    cut_index = max(0, min(len(dates) - 1, int(round(len(dates) * in_sample_fraction)) - 1))
    boundary = dates[cut_index]
    in_sample = [inst for inst in instances if inst.session <= boundary]
    out_of_sample = [inst for inst in instances if inst.session > boundary]
    return in_sample, out_of_sample, boundary


# ---------------------------------------------------------------------------
# DB-backed full backtest runner (bounded enumeration + per-instance reads).
# ---------------------------------------------------------------------------
@dataclass
class GapUpBacktestConfig:
    db_path: str
    max_symbols: int = 0  # 0 = all tables (full universe)
    in_sample_fraction: float = 0.7
    cost_bps: float = COST_BPS_ROUND_TRIP
    entry_threshold: float = ENTRY_CHANGE_RATE_THRESHOLD
    tp_grid: Tuple[float, ...] = TP_GRID_PCT
    sl_grid: Tuple[float, ...] = SL_GRID_PCT
    artifacts_dir: Optional[str] = None


@dataclass
class GapUpBacktestResult:
    instances: List[GapUpInstance] = field(default_factory=list)
    n_symbols: int = 0
    n_sessions: int = 0
    date_min: Optional[str] = None
    date_max: Optional[str] = None
    boundary_date: Optional[str] = None
    grid: List[Dict[str, Any]] = field(default_factory=list)
    baseline: Dict[str, Any] = field(default_factory=dict)


def collect_gap_up_instances(
    config: GapUpBacktestConfig,
) -> List[GapUpInstance]:
    """Enumerate tables, read each table's sessions, collect gap-up instances.

    Reads are bounded: one session-prefix-indexed morning-window query per
    (symbol, session).  Never materialises a full table.
    """

    conn = connect_readonly(config.db_path)
    instances: List[GapUpInstance] = []
    try:
        tables = list_stock_tables(
            conn, max_tables=config.max_symbols if config.max_symbols > 0 else None
        )
        for table in tables:
            columns = get_table_columns(conn, table)
            ts_col = _resolve_column(columns, _TIMESTAMP_CANDIDATES)
            px_col = _resolve_column(columns, _PRICE_CANDIDATES)
            cr_col = _resolve_column(columns, _CHANGE_RATE_CANDIDATES)
            if not ts_col or not px_col or not cr_col:
                continue  # table lacks the required columns; skip honestly
            qt = _quote_ident(table)
            ts_q = _quote_ident(ts_col)
            date_query = f"SELECT DISTINCT substr(CAST({ts_q} AS TEXT), 1, 8) FROM {qt}"
            session_dates = [
                str(row[0])
                for row in conn.execute(date_query).fetchall()
                if row[0] is not None and len(str(row[0])) == 8 and str(row[0]).isdigit()
            ]
            for session in sorted(session_dates):
                inst = read_gap_up_instance(
                    conn,
                    table,
                    session,
                    timestamp_col=ts_col,
                    price_col=px_col,
                    change_rate_col=cr_col,
                    entry_threshold=config.entry_threshold,
                )
                if inst is not None:
                    instances.append(inst)
    finally:
        conn.close()
    return instances


def run_gap_up_backtest(config: GapUpBacktestConfig) -> GapUpBacktestResult:
    """Run the full pre-registered gap-up backtest and return the result.

    Computes the per-TP/SL-combo metrics on BOTH the in-sample and out-of-sample
    split, plus the no-TP/SL baseline on each split.  No cell is selected as
    "the" answer here — the caller renders the full surface.
    """

    instances = collect_gap_up_instances(config)
    result = GapUpBacktestResult(instances=instances)
    if not instances:
        return result

    result.n_symbols = len({inst.symbol for inst in instances})
    sessions = {inst.session for inst in instances}
    result.n_sessions = len({(inst.symbol, inst.session) for inst in instances})
    result.date_min = min(sessions)
    result.date_max = max(sessions)

    in_sample, out_sample, boundary = split_instances_by_date(
        instances, in_sample_fraction=config.in_sample_fraction
    )
    result.boundary_date = boundary

    def _eval(insts: Sequence[GapUpInstance], tp: float, sl: float) -> Dict[str, Any]:
        trades = [
            simulate_trade(
                inst.prices,
                tp_pct=tp,
                sl_pct=sl,
                cost_bps=config.cost_bps,
                seconds=inst.seconds,
            )
            for inst in insts
        ]
        return aggregate_trades(trades)

    def _baseline(insts: Sequence[GapUpInstance]) -> Dict[str, Any]:
        trades = [
            simulate_baseline(inst.prices, cost_bps=config.cost_bps, seconds=inst.seconds)
            for inst in insts
        ]
        return aggregate_trades(trades)

    grid: List[Dict[str, Any]] = []
    for tp in config.tp_grid:
        for sl in config.sl_grid:
            grid.append(
                {
                    "tp_pct": tp,
                    "sl_pct": sl,
                    "in_sample": _eval(in_sample, tp, sl),
                    "out_of_sample": _eval(out_sample, tp, sl),
                    "all": _eval(instances, tp, sl),
                }
            )
    result.grid = grid
    result.baseline = {
        "in_sample": _baseline(in_sample),
        "out_of_sample": _baseline(out_sample),
        "all": _baseline(instances),
    }

    if config.artifacts_dir:
        _write_artifacts(config, result, in_sample, out_sample)

    return result


def _write_artifacts(
    config: GapUpBacktestConfig,
    result: GapUpBacktestResult,
    in_sample: Sequence[GapUpInstance],
    out_sample: Sequence[GapUpInstance],
) -> None:
    """Write per-instance trades (gitignored) for audit."""

    out_dir = Path(config.artifacts_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    split_label = {id(inst): "in_sample" for inst in in_sample}
    split_label.update({id(inst): "out_of_sample" for inst in out_sample})

    rows: List[Dict[str, Any]] = []
    for inst in result.instances:
        rec: Dict[str, Any] = {
            "symbol": inst.symbol,
            "session": inst.session,
            "split": split_label.get(id(inst), "unknown"),
            "entry_change_rate": inst.entry_change_rate,
            "entry_price": inst.entry_price,
            "n_path_bars": len(inst.prices),
        }
        for tp in config.tp_grid:
            for sl in config.sl_grid:
                tr = simulate_trade(
                    inst.prices,
                    tp_pct=tp,
                    sl_pct=sl,
                    cost_bps=config.cost_bps,
                    seconds=inst.seconds,
                )
                key = f"tp{tp:g}_sl{sl:g}"
                rec[f"{key}_reason"] = tr.exit_reason
                rec[f"{key}_net_pct"] = round(tr.net_return_pct, 6)
        base = simulate_baseline(inst.prices, cost_bps=config.cost_bps, seconds=inst.seconds)
        rec["baseline_net_pct"] = round(base.net_return_pct, 6)
        rec["baseline_hold_seconds"] = base.hold_seconds
        rows.append(rec)

    (out_dir / "instances.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = {
        "n_instances": len(result.instances),
        "n_symbols": result.n_symbols,
        "n_sessions": result.n_sessions,
        "date_min": result.date_min,
        "date_max": result.date_max,
        "boundary_date": result.boundary_date,
        "cost_bps": config.cost_bps,
        "entry_threshold": config.entry_threshold,
        "tp_grid": list(config.tp_grid),
        "sl_grid": list(config.sl_grid),
        "grid": result.grid,
        "baseline": result.baseline,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _format_metrics(m: Dict[str, Any]) -> str:
    if not m or m.get("n_trades", 0) == 0:
        return "n=0"
    return (
        f"n={m['n_trades']} win={m['win_rate']:.1%} "
        f"mean_net={m['mean_net_return_pct']:+.3f}% "
        f"exp={m['expectancy_pct']:+.3f}% "
        f"hold={m['avg_hold_seconds']:.0f}s "
        f"tp/sl/time={m['exit_mix'][EXIT_TP]:.0%}/{m['exit_mix'][EXIT_SL]:.0%}/{m['exit_mix'][EXIT_TIME]:.0%}"
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Opening gap-up momentum backtest (시초 갭상승) on the 1s STOM DB."
    )
    parser.add_argument(
        "--db",
        default=str(PROJECT_ROOT / "_database" / "stock_tick_back.db"),
        help="Path to stock_tick_back.db.",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=0,
        help="Bound the number of symbol tables scanned (0 = full universe).",
    )
    parser.add_argument(
        "--in-sample-fraction",
        type=float,
        default=0.7,
        help="Fraction of distinct session dates used as in-sample (earlier).",
    )
    parser.add_argument("--cost-bps", type=float, default=COST_BPS_ROUND_TRIP)
    parser.add_argument(
        "--artifacts-dir",
        default=str(PROJECT_ROOT / ".omx" / "artifacts" / "gap_up_backtest"),
        help="Where to write per-instance trade artifacts (gitignored).",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional path to write the full result summary as JSON.",
    )
    args = parser.parse_args(argv)

    config = GapUpBacktestConfig(
        db_path=args.db,
        max_symbols=args.max_symbols,
        in_sample_fraction=args.in_sample_fraction,
        cost_bps=args.cost_bps,
        artifacts_dir=args.artifacts_dir,
    )
    result = run_gap_up_backtest(config)

    print("=== 시초 갭상승 (opening gap-up) backtest ===")
    print(
        f"instances={len(result.instances)} symbols={result.n_symbols} "
        f"sessions={result.n_sessions} dates={result.date_min}->{result.date_max} "
        f"boundary={result.boundary_date}"
    )
    print(f"entry: 등락율>={config.entry_threshold}%  time-exit={TIME_EXIT_HHMMSS}  cost={config.cost_bps}bp")
    print("-- baseline (buy@open hold->09:25 no TP/SL) --")
    print(f"  in-sample : {_format_metrics(result.baseline.get('in_sample', {}))}")
    print(f"  out-sample: {_format_metrics(result.baseline.get('out_of_sample', {}))}")
    print("-- TP/SL grid (in-sample | out-of-sample) --")
    for cell in result.grid:
        print(
            f"  TP={cell['tp_pct']:g}% SL={cell['sl_pct']:g}%  "
            f"IS[{_format_metrics(cell['in_sample'])}]  "
            f"OOS[{_format_metrics(cell['out_of_sample'])}]"
        )

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "n_instances": len(result.instances),
                    "n_symbols": result.n_symbols,
                    "n_sessions": result.n_sessions,
                    "date_min": result.date_min,
                    "date_max": result.date_max,
                    "boundary_date": result.boundary_date,
                    "cost_bps": config.cost_bps,
                    "entry_threshold": config.entry_threshold,
                    "tp_grid": list(config.tp_grid),
                    "sl_grid": list(config.sl_grid),
                    "grid": result.grid,
                    "baseline": result.baseline,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"wrote summary -> {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
