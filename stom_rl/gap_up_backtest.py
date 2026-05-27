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
* **Cost** — a configurable round-trip model
  (:func:`round_trip_cost_bps`):
  ``commission_bps_per_side*2 + transaction_tax_bps (SELL side only)
  + slippage_bps``.  The legacy flat 25 bp is the default total; a cost SWEEP
  over ``{0,5,10,15,18,25}`` bp is run to report the BREAKEVEN round-trip cost
  at which OOS net expectancy crosses zero (a property, not a tuned cell).
* **Entry filters (optional, pre-registered from STOM buy rules)** — on top of
  the 등락율>=2% gate, optionally require causal ENTRY-BAR demand signals:
  ``체결강도``(trade_strength) and 호가 ``bid_ask_imbalance``
  (매수총잔량/(매수+매도총잔량)).  Filters use only entry-bar values (<= entry
  second), so there is no look-ahead.  Definitions are pre-registered
  (:data:`ENTRY_FILTERS`), drawn from ``stom_rl/rules/buy_demand_pressure.json``
  / ``buy_widev1.json`` — NOT searched for the best threshold.

Honesty caveats (locked, see the doc)
-------------------------------------
* The TP/SL pair is SWEPT over a small grid (``TP x SL``); the full surface
  is reported and no single cell is cherry-picked as "the" answer.
* The cost sweep reports the BREAKEVEN cost (where OOS expectancy = 0), not a
  cherry-picked low-cost cell, and the entry filters are pre-registered (no
  threshold search).
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
COST_BPS_ROUND_TRIP: float = 25.0  # entry + exit combined, basis points (legacy flat)

# Swept TP/SL grid (M = 16 combos).  Reported in full; no cherry-pick.
TP_GRID_PCT: Tuple[float, ...] = (1.0, 2.0, 3.0, 5.0)
SL_GRID_PCT: Tuple[float, ...] = (1.0, 1.5, 2.0, 3.0)

# Cost SWEEP of round-trip levels (bps).  Used to locate the breakeven cost
# (OOS net expectancy = 0).  Includes the two labelled reference scenarios:
#   * Korean-domestic ~18 bp  (commission ~1.5 bp/side + transaction tax ~15 bp
#     on the SELL side only); see KOREAN_DOMESTIC_COST.
#   * International / low ~5 bp (commission ~2.5 bp/side, no transaction tax);
#     see INTERNATIONAL_LOW_COST.
COST_SWEEP_BPS: Tuple[float, ...] = (0.0, 5.0, 10.0, 15.0, 18.0, 25.0)

# Pre-registered entry filters (NOT threshold-searched).  Thresholds are the
# STOM canonical values (체결강도 >= 100 = "at par", 호가 imbalance >= 0.5 =
# "bid-side leaning") taken verbatim from buy_widev1.json / buy_demand_pressure
# .json — NOT tuned on this backtest's results.
TRADE_STRENGTH_THRESHOLD: float = 100.0  # 체결강도 >= 100 (STOM "at par")
IMBALANCE_THRESHOLD: float = 0.5  # 호가 매수총잔량/(매수+매도총잔량) >= 0.5

# DB column resolution (Korean names stored UTF-8; sqlite3 decodes by default).
_TIMESTAMP_CANDIDATES: Tuple[str, ...] = ("index", "timestamps", "timestamp")
_PRICE_CANDIDATES: Tuple[str, ...] = ("현재가", "종가", "close")
_CHANGE_RATE_CANDIDATES: Tuple[str, ...] = ("등락율",)
_TRADE_STRENGTH_CANDIDATES: Tuple[str, ...] = ("체결강도",)
_SEC_AMOUNT_CANDIDATES: Tuple[str, ...] = ("초당거래대금",)
_BID_QTY_CANDIDATES: Tuple[str, ...] = ("매수총잔량",)
_ASK_QTY_CANDIDATES: Tuple[str, ...] = ("매도총잔량",)

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
# Realistic round-trip cost model (commission + sell-side tax + slippage).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RoundTripCost:
    """A realistic per-round-trip cost model (all components in basis points).

    A round trip is one BUY (entry) + one SELL (exit).  The total round-trip
    cost is::

        commission_bps_per_side * 2      (commission charged on BOTH sides)
        + transaction_tax_bps            (Korean 증권거래세 — SELL side ONLY)
        + slippage_bps                   (round-trip execution slippage)

    The transaction tax is applied ONCE (sell side only); buying incurs no
    transaction tax in the Korean market, hence it is not multiplied by two.
    """

    commission_bps_per_side: float = 0.0
    transaction_tax_bps: float = 0.0  # sell side only
    slippage_bps: float = 0.0

    def total_round_trip_bps(self) -> float:
        return round_trip_cost_bps(
            commission_bps_per_side=self.commission_bps_per_side,
            transaction_tax_bps=self.transaction_tax_bps,
            slippage_bps=self.slippage_bps,
        )


def round_trip_cost_bps(
    *,
    commission_bps_per_side: float = 0.0,
    transaction_tax_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> float:
    """Compute the total round-trip cost in basis points.

    ``commission_bps_per_side`` is charged on BOTH the buy and the sell, so it
    is doubled.  ``transaction_tax_bps`` (증권거래세) is charged on the SELL side
    ONLY, so it is added once.  ``slippage_bps`` is the round-trip slippage.
    """

    if (
        commission_bps_per_side < 0
        or transaction_tax_bps < 0
        or slippage_bps < 0
    ):
        raise ValueError("cost components must be non-negative")
    return (
        commission_bps_per_side * 2.0
        + transaction_tax_bps
        + slippage_bps
    )


# Two labelled reference scenarios (see COST_SWEEP_BPS docstring).
# Korean-domestic: commission ~1.5 bp/side + 증권거래세 ~15 bp (sell only)
#   -> 1.5*2 + 15 = 18 bp round trip.
KOREAN_DOMESTIC_COST = RoundTripCost(
    commission_bps_per_side=1.5, transaction_tax_bps=15.0, slippage_bps=0.0
)
# International / low: commission ~2.5 bp/side, no transaction tax
#   -> 2.5*2 + 0 = 5 bp round trip.
INTERNATIONAL_LOW_COST = RoundTripCost(
    commission_bps_per_side=2.5, transaction_tax_bps=0.0, slippage_bps=0.0
)


# ---------------------------------------------------------------------------
# Pre-registered causal entry filters (STOM buy-rule derived; NOT searched).
# ---------------------------------------------------------------------------
def compute_bid_ask_imbalance(
    bid_total_qty: Optional[float], ask_total_qty: Optional[float]
) -> Optional[float]:
    """호가 imbalance = 매수총잔량 / (매수총잔량 + 매도총잔량).

    Returns ``None`` when either side is missing or the book is empty (no
    denominator).  Range is ``[0, 1]``; ``>= 0.5`` means the book leans bid-side
    (more resting buy interest), the STOM 호가상승압력 intent.
    """

    if bid_total_qty is None or ask_total_qty is None:
        return None
    try:
        bid = float(bid_total_qty)
        ask = float(ask_total_qty)
    except (TypeError, ValueError):
        return None
    denom = bid + ask
    if denom <= 0:
        return None
    return bid / denom


@dataclass(frozen=True)
class EntryFilter:
    """A pre-registered causal entry filter (evaluated on the ENTRY BAR only)."""

    name: str
    require_trade_strength: bool = False
    require_imbalance: bool = False
    trade_strength_threshold: float = TRADE_STRENGTH_THRESHOLD
    imbalance_threshold: float = IMBALANCE_THRESHOLD


# Pre-registered filter set.  "none" = baseline (등락율>=2% only); F1/F2 are the
# STOM demand gates.  These are FIXED definitions (no per-result tuning).
ENTRY_FILTERS: Dict[str, EntryFilter] = {
    "none": EntryFilter(name="none"),
    # F1: 체결강도 >= 100 (STOM buy_widev1 / buy_demand_pressure "at par").
    "ts": EntryFilter(name="ts", require_trade_strength=True),
    # F2: 체결강도 >= 100 AND 호가 imbalance >= 0.5 (full buy_demand_pressure).
    "ts_imb": EntryFilter(
        name="ts_imb", require_trade_strength=True, require_imbalance=True
    ),
}


def passes_entry_filter(
    inst: "GapUpInstance", entry_filter: EntryFilter
) -> bool:
    """Return True if the instance's ENTRY-BAR signals satisfy the filter.

    Uses ONLY the entry-bar (<= entry second) ``trade_strength`` and
    ``bid_ask_imbalance`` already captured on the instance, so there is no
    look-ahead.  A required signal that is missing (``None``) FAILS the filter
    (we do not silently admit instances lacking the demand evidence).
    """

    if entry_filter.require_trade_strength:
        ts = inst.entry_trade_strength
        if ts is None or ts < entry_filter.trade_strength_threshold:
            return False
    if entry_filter.require_imbalance:
        imb = inst.entry_bid_ask_imbalance
        if imb is None or imb < entry_filter.imbalance_threshold:
            return False
    return True


def filter_instances(
    instances: Sequence["GapUpInstance"], entry_filter: EntryFilter
) -> List["GapUpInstance"]:
    """Apply a pre-registered entry filter, returning the surviving instances."""

    return [inst for inst in instances if passes_entry_filter(inst, entry_filter)]


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
    """A resolved gap-up entry candidate for one (symbol, session).

    ``entry_trade_strength`` (체결강도), ``entry_sec_amount`` (초당거래대금) and
    ``entry_bid_ask_imbalance`` are the CAUSAL entry-bar demand signals used by
    :func:`passes_entry_filter`; all are taken from the FIRST (entry) bar only,
    so they never look ahead.  Any may be ``None`` when the source column is
    absent or unreadable.
    """

    symbol: str
    session: str
    entry_change_rate: float
    entry_price: float
    prices: Tuple[float, ...]
    seconds: Tuple[int, ...]
    entry_trade_strength: Optional[float] = None
    entry_sec_amount: Optional[float] = None
    entry_bid_ask_imbalance: Optional[float] = None


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
    trade_strength_col: Optional[str] = None,
    sec_amount_col: Optional[str] = None,
    bid_qty_col: Optional[str] = None,
    ask_qty_col: Optional[str] = None,
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

    When the optional demand columns (``trade_strength_col`` = 체결강도,
    ``sec_amount_col`` = 초당거래대금, ``bid_qty_col``/``ask_qty_col`` =
    매수/매도총잔량) are supplied they are read from the ENTRY bar ONLY and stored
    on the instance for the causal entry filters (no look-ahead).
    """

    if len(session) != 8 or not session.isdigit():
        raise ValueError(f"session must be YYYYMMDD, got: {session}")
    qt = _quote_ident(table)
    ts_q = _quote_ident(timestamp_col)
    px_q = _quote_ident(price_col)
    cr_q = _quote_ident(change_rate_col)
    # Optional demand columns appended AFTER the core three (entry-bar only).
    extra_cols = [trade_strength_col, sec_amount_col, bid_qty_col, ask_qty_col]
    select_extra = "".join(
        f", {_quote_ident(c)}" if c else ", NULL" for c in extra_cols
    )
    start_full = int(session + session_start)
    end_full = int(session + time_exit)
    query = (
        f"SELECT {ts_q}, {px_q}, {cr_q}{select_extra} FROM {qt} "
        f"WHERE {ts_q} >= ? AND {ts_q} <= ? "
        f"ORDER BY {ts_q}"
    )
    rows = conn.execute(query, (start_full, end_full)).fetchall()
    if not rows:
        return None

    # Entry = first bar of the session window.
    entry_row = rows[0]
    entry_px, entry_cr = entry_row[1], entry_row[2]
    if entry_cr is None or entry_px is None:
        return None
    try:
        entry_cr = float(entry_cr)
        entry_px = float(entry_px)
    except (TypeError, ValueError):
        return None
    if entry_px <= 0 or entry_cr < float(entry_threshold):
        return None

    # CAUSAL entry-bar demand signals (entry row only; never look ahead).
    def _opt_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    entry_trade_strength = _opt_float(entry_row[3])
    entry_sec_amount = _opt_float(entry_row[4])
    entry_bid_qty = _opt_float(entry_row[5])
    entry_ask_qty = _opt_float(entry_row[6])
    entry_imbalance = compute_bid_ask_imbalance(entry_bid_qty, entry_ask_qty)

    prices: List[float] = []
    secs: List[int] = []
    for row in rows:
        ts, px = row[0], row[1]
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
        entry_trade_strength=entry_trade_strength,
        entry_sec_amount=entry_sec_amount,
        entry_bid_ask_imbalance=entry_imbalance,
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
# Cost sweep + breakeven (the breakeven is a PROPERTY, not a tuned cell).
# ---------------------------------------------------------------------------
def expectancy_at_cost(
    instances: Sequence[GapUpInstance],
    *,
    tp_pct: float,
    sl_pct: float,
    cost_bps: float,
) -> Optional[float]:
    """Net per-trade expectancy (%) for one TP/SL at one round-trip cost.

    Returns ``None`` for an empty instance set.  Because cost enters the net
    return purely additively (``net = gross - cost%``), expectancy is exactly
    ``gross_expectancy - cost_bps/100`` and STRICTLY DECREASES as cost rises —
    this monotonicity is what makes the breakeven well-defined.
    """

    if not instances:
        return None
    trades = [
        simulate_trade(
            inst.prices,
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            cost_bps=cost_bps,
            seconds=inst.seconds,
        )
        for inst in instances
    ]
    return aggregate_trades(trades)["expectancy_pct"]


def breakeven_round_trip_bps(
    instances: Sequence[GapUpInstance],
    *,
    tp_pct: float,
    sl_pct: float,
) -> Optional[float]:
    """Round-trip cost (bps) at which net expectancy crosses 0 for this TP/SL.

    Net expectancy = ``gross_expectancy_pct - cost_bps/100``; it is 0 exactly
    when ``cost_bps = gross_expectancy_pct * 100``.  A NEGATIVE result means even
    a zero-cost trade loses (gross edge < 0) — the strategy is unprofitable at
    ANY cost.  A POSITIVE result is the maximum tolerable round-trip cost.
    Returns ``None`` for an empty set.
    """

    gross = expectancy_at_cost(
        instances, tp_pct=tp_pct, sl_pct=sl_pct, cost_bps=0.0
    )
    if gross is None:
        return None
    return gross * 100.0  # %/trade -> bps


def cost_sweep_table(
    instances: Sequence[GapUpInstance],
    *,
    tp_pct: float,
    sl_pct: float,
    cost_levels: Sequence[float] = COST_SWEEP_BPS,
) -> List[Dict[str, Any]]:
    """OOS-honest cost sweep: net expectancy at each round-trip cost level."""

    return [
        {
            "cost_bps": float(c),
            "expectancy_pct": expectancy_at_cost(
                instances, tp_pct=tp_pct, sl_pct=sl_pct, cost_bps=float(c)
            ),
        }
        for c in cost_levels
    ]


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
    # Cost-sweep + filter analysis (the prior best cell is the PRIMARY TP/SL).
    cost_sweep_bps: Tuple[float, ...] = COST_SWEEP_BPS
    primary_tp_pct: float = 5.0  # prior "best OOS" cell (TP5/SL1), reported only
    primary_sl_pct: float = 1.0
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
    # Cost-sweep x filter analysis (keyed by filter name "none"/"ts"/"ts_imb").
    filter_analysis: List[Dict[str, Any]] = field(default_factory=list)


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
            # Optional causal demand columns (None when absent -> filter NULLs).
            ts_strength_col = _resolve_column(columns, _TRADE_STRENGTH_CANDIDATES)
            sec_amount_col = _resolve_column(columns, _SEC_AMOUNT_CANDIDATES)
            bid_qty_col = _resolve_column(columns, _BID_QTY_CANDIDATES)
            ask_qty_col = _resolve_column(columns, _ASK_QTY_CANDIDATES)
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
                    trade_strength_col=ts_strength_col,
                    sec_amount_col=sec_amount_col,
                    bid_qty_col=bid_qty_col,
                    ask_qty_col=ask_qty_col,
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

    # ---- Cost-sweep x entry-filter analysis (PRIMARY TP/SL, OOS-honest) ----
    # For each pre-registered filter, report: surviving N (IS/OOS), the
    # breakeven round-trip cost (IS & OOS), and the net expectancy at every
    # swept cost level (IS & OOS).  The breakeven is a PROPERTY (gross edge x
    # 100), so reporting it across filters is not cherry-picking.
    tp_p, sl_p = config.primary_tp_pct, config.primary_sl_pct
    filter_analysis: List[Dict[str, Any]] = []
    for fname, efilter in ENTRY_FILTERS.items():
        is_f = filter_instances(in_sample, efilter)
        oos_f = filter_instances(out_sample, efilter)
        all_f = filter_instances(instances, efilter)
        filter_analysis.append(
            {
                "filter": fname,
                "n_in_sample": len(is_f),
                "n_out_of_sample": len(oos_f),
                "n_all": len(all_f),
                "primary_tp_pct": tp_p,
                "primary_sl_pct": sl_p,
                "breakeven_bps_in_sample": breakeven_round_trip_bps(
                    is_f, tp_pct=tp_p, sl_pct=sl_p
                ),
                "breakeven_bps_out_of_sample": breakeven_round_trip_bps(
                    oos_f, tp_pct=tp_p, sl_pct=sl_p
                ),
                "sweep_in_sample": cost_sweep_table(
                    is_f, tp_pct=tp_p, sl_pct=sl_p, cost_levels=config.cost_sweep_bps
                ),
                "sweep_out_of_sample": cost_sweep_table(
                    oos_f, tp_pct=tp_p, sl_pct=sl_p, cost_levels=config.cost_sweep_bps
                ),
            }
        )
    result.filter_analysis = filter_analysis

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
        "cost_sweep_bps": list(config.cost_sweep_bps),
        "primary_tp_pct": config.primary_tp_pct,
        "primary_sl_pct": config.primary_sl_pct,
        "grid": result.grid,
        "baseline": result.baseline,
        "filter_analysis": result.filter_analysis,
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

    # Cost-sweep x filter (PRIMARY TP/SL) + breakeven round-trip cost.
    if result.filter_analysis:
        tp_p, sl_p = config.primary_tp_pct, config.primary_sl_pct
        levels = list(config.cost_sweep_bps)
        print(
            f"-- cost sweep x entry filter (PRIMARY TP={tp_p:g}%/SL={sl_p:g}%) --"
        )
        print(
            "   ref scenarios: Korean-domestic="
            f"{KOREAN_DOMESTIC_COST.total_round_trip_bps():g}bp "
            f"(comm {KOREAN_DOMESTIC_COST.commission_bps_per_side:g}bp/side x2 "
            f"+ tax {KOREAN_DOMESTIC_COST.transaction_tax_bps:g}bp sell-only), "
            "international/low="
            f"{INTERNATIONAL_LOW_COST.total_round_trip_bps():g}bp "
            f"(comm {INTERNATIONAL_LOW_COST.commission_bps_per_side:g}bp/side x2, no tax)"
        )
        header = "  filter    N(IS/OOS)  breakeven(IS/OOS)bp  " + " ".join(
            f"OOS@{int(c)}bp" for c in levels
        )
        print(header)
        for fa in result.filter_analysis:
            sweep = {row["cost_bps"]: row["expectancy_pct"] for row in fa["sweep_out_of_sample"]}

            def _fmt_exp(v: Optional[float]) -> str:
                return "  n=0  " if v is None else f"{v:+.3f}"

            def _fmt_be(v: Optional[float]) -> str:
                return "n/a" if v is None else f"{v:+.1f}"

            cells = " ".join(f"{_fmt_exp(sweep.get(c)):>8}" for c in levels)
            print(
                f"  {fa['filter']:<8}  {fa['n_in_sample']}/{fa['n_out_of_sample']:<6}  "
                f"{_fmt_be(fa['breakeven_bps_in_sample'])}/"
                f"{_fmt_be(fa['breakeven_bps_out_of_sample'])}        {cells}"
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
                    "cost_sweep_bps": list(config.cost_sweep_bps),
                    "primary_tp_pct": config.primary_tp_pct,
                    "primary_sl_pct": config.primary_sl_pct,
                    "grid": result.grid,
                    "baseline": result.baseline,
                    "filter_analysis": result.filter_analysis,
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
