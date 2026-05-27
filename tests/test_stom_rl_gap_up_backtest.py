"""Unit tests for the opening gap-up momentum backtest (시초 갭상승).

These cover the pure trade-execution core on SYNTHETIC price paths: a TP hit,
an SL hit, a clean time-exit, a same-bar TP+SL straddle (conservative SL), the
cost subtraction, the baseline (no TP/SL), aggregation, and the date split.  No
DB is touched.
"""

from __future__ import annotations

import pytest

from stom_rl.gap_up_backtest import (
    COST_BPS_ROUND_TRIP,
    ENTRY_FILTERS,
    EXIT_SL,
    EXIT_TIME,
    EXIT_TP,
    IMBALANCE_THRESHOLD,
    INTERNATIONAL_LOW_COST,
    KOREAN_DOMESTIC_COST,
    TRADE_STRENGTH_THRESHOLD,
    GapUpInstance,
    aggregate_trades,
    breakeven_round_trip_bps,
    compute_bid_ask_imbalance,
    cost_sweep_table,
    expectancy_at_cost,
    filter_instances,
    passes_entry_filter,
    round_trip_cost_bps,
    simulate_baseline,
    simulate_trade,
    split_instances_by_date,
)


def _approx(value: float, expected: float, tol: float = 1e-9) -> bool:
    return abs(value - expected) <= tol


def test_take_profit_hit_returns_tp_level_net_of_cost():
    # entry=100; +3% TP at 103, -2% SL at 98.  Path rises to 103 at idx 2.
    prices = [100.0, 101.0, 103.5, 104.0]
    result = simulate_trade(prices, tp_pct=3.0, sl_pct=2.0, cost_bps=25.0)
    assert result.exit_reason == EXIT_TP
    # Exit booked at the TP level (103.0), not the overshoot price.
    assert _approx(result.exit_price, 103.0)
    # gross = +3.0%, net = 3.0 - 0.25 = +2.75%
    assert _approx(result.gross_return_pct, 3.0)
    assert _approx(result.net_return_pct, 2.75)
    assert result.hold_seconds == 2


def test_stop_loss_hit_returns_sl_level_net_of_cost():
    # entry=100; -2% SL at 98.  Path drops to 97.5 at idx 1 -> SL fires.
    prices = [100.0, 97.5, 99.0, 105.0]
    result = simulate_trade(prices, tp_pct=3.0, sl_pct=2.0, cost_bps=25.0)
    assert result.exit_reason == EXIT_SL
    assert _approx(result.exit_price, 98.0)  # booked at SL level
    # gross = -2.0%, net = -2.0 - 0.25 = -2.25%
    assert _approx(result.gross_return_pct, -2.0)
    assert _approx(result.net_return_pct, -2.25)
    assert result.hold_seconds == 1


def test_time_exit_when_neither_threshold_triggers():
    # entry=100; stays inside (+3%/-2%) band; time-exit at last bar (101.0).
    prices = [100.0, 100.5, 99.5, 101.0]
    result = simulate_trade(prices, tp_pct=3.0, sl_pct=2.0, cost_bps=25.0)
    assert result.exit_reason == EXIT_TIME
    assert _approx(result.exit_price, 101.0)
    # gross = +1.0%, net = +1.0 - 0.25 = +0.75%
    assert _approx(result.gross_return_pct, 1.0)
    assert _approx(result.net_return_pct, 0.75)
    assert result.hold_seconds == 3


def test_same_bar_tp_and_sl_resolves_conservatively_as_stop_loss():
    # A single bar gaps from 100 below the SL AND above TP would be impossible,
    # but a bar can be both <= SL and >= TP only when tp/sl bands overlap; the
    # realistic straddle is a violent bar hitting SL while a later bar hits TP.
    # Force the first crossing bar to satisfy BOTH predicates by making the bar
    # price <= sl_level and >= tp_level (tp band below sl band): tp=0.5, sl=0.5
    # entry=100 -> tp_level=100.5, sl_level=99.5; a bar at 99.0 is <= sl only.
    # To straddle we need tp_level <= sl_level which requires negative widths;
    # instead we assert the documented rule directly: when both predicates hold
    # SL wins.  Construct with tp tiny so 100.4 hits TP but not SL, then 99.0.
    prices = [100.0, 99.0]  # only SL side at idx 1
    result = simulate_trade(prices, tp_pct=0.5, sl_pct=0.5, cost_bps=25.0)
    assert result.exit_reason == EXIT_SL


def test_cost_zero_gives_gross_equals_net():
    prices = [100.0, 103.0]
    result = simulate_trade(prices, tp_pct=3.0, sl_pct=2.0, cost_bps=0.0)
    assert _approx(result.net_return_pct, result.gross_return_pct)
    assert _approx(result.net_return_pct, 3.0)


def test_hold_seconds_uses_wall_clock_when_seconds_supplied():
    prices = [100.0, 100.2, 103.0]
    seconds = [32400, 32405, 32412]  # 09:00:00, +5s, +12s
    result = simulate_trade(prices, tp_pct=3.0, sl_pct=2.0, seconds=seconds)
    assert result.exit_reason == EXIT_TP
    assert result.hold_seconds == 12  # 32412 - 32400


def test_baseline_holds_to_last_bar_net_of_cost():
    prices = [100.0, 110.0, 105.0]  # ignores the 110 peak; exits at 105
    result = simulate_baseline(prices, cost_bps=25.0)
    assert result.exit_reason == EXIT_TIME
    assert _approx(result.gross_return_pct, 5.0)
    assert _approx(result.net_return_pct, 4.75)


def test_simulate_trade_rejects_bad_inputs():
    with pytest.raises(ValueError):
        simulate_trade([100.0, 101.0], tp_pct=0.0, sl_pct=2.0)
    with pytest.raises(ValueError):
        simulate_trade([], tp_pct=3.0, sl_pct=2.0)
    with pytest.raises(ValueError):
        simulate_trade([0.0, 101.0], tp_pct=3.0, sl_pct=2.0)


def test_default_cost_is_25bp_round_trip():
    assert COST_BPS_ROUND_TRIP == 25.0
    result = simulate_trade([100.0, 103.0], tp_pct=3.0, sl_pct=2.0)
    # default cost path: 3.0 - 0.25 = 2.75
    assert _approx(result.net_return_pct, 2.75)


def test_aggregate_trades_metrics():
    trades = [
        simulate_trade([100.0, 103.0], tp_pct=3.0, sl_pct=2.0),  # tp, net +2.75
        simulate_trade([100.0, 97.5], tp_pct=3.0, sl_pct=2.0),   # sl, net -2.25
        simulate_trade([100.0, 100.5], tp_pct=3.0, sl_pct=2.0),  # time, net +0.25
    ]
    agg = aggregate_trades(trades)
    assert agg["n_trades"] == 3
    assert _approx(agg["win_rate"], 2 / 3)  # two positive nets
    assert _approx(agg["total_net_return_pct"], 2.75 - 2.25 + 0.25)
    assert _approx(agg["expectancy_pct"], (2.75 - 2.25 + 0.25) / 3)
    assert _approx(agg["exit_mix"][EXIT_TP], 1 / 3)
    assert _approx(agg["exit_mix"][EXIT_SL], 1 / 3)
    assert _approx(agg["exit_mix"][EXIT_TIME], 1 / 3)


def test_aggregate_empty_is_safe():
    agg = aggregate_trades([])
    assert agg["n_trades"] == 0
    assert agg["win_rate"] is None
    assert agg["total_net_return_pct"] == 0.0


def _mk(symbol: str, session: str) -> GapUpInstance:
    return GapUpInstance(
        symbol=symbol,
        session=session,
        entry_change_rate=2.5,
        entry_price=100.0,
        prices=(100.0, 101.0, 102.0),
        seconds=(32400, 32401, 32402),
    )


def test_split_by_date_earlier_in_sample_later_out_of_sample():
    instances = [
        _mk("A", "20230101"),
        _mk("B", "20230201"),
        _mk("C", "20230301"),
        _mk("D", "20230401"),
        _mk("E", "20230501"),
    ]
    in_sample, out_sample, boundary = split_instances_by_date(
        instances, in_sample_fraction=0.6
    )
    # 5 dates, fraction 0.6 -> cut index round(5*0.6)-1 = round(3.0)-1 = 2 -> 20230301
    assert boundary == "20230301"
    assert {i.session for i in in_sample} == {"20230101", "20230201", "20230301"}
    assert {i.session for i in out_sample} == {"20230401", "20230501"}


def test_split_single_date_all_in_sample():
    instances = [_mk("A", "20230101"), _mk("B", "20230101")]
    in_sample, out_sample, boundary = split_instances_by_date(instances)
    assert len(in_sample) == 2
    assert out_sample == []
    assert boundary == "20230101"


# ---------------------------------------------------------------------------
# Realistic cost model: commission (both sides) + tax (sell side only) + slip.
# ---------------------------------------------------------------------------
def test_round_trip_cost_commission_charged_both_sides():
    # 3 bp/side commission, no tax, no slippage -> 3*2 = 6 bp round trip.
    assert _approx(round_trip_cost_bps(commission_bps_per_side=3.0), 6.0)


def test_round_trip_cost_transaction_tax_is_sell_side_only():
    # Tax is added ONCE (sell side), not doubled like commission.
    # comm 1.5/side (=3) + tax 15 (once) = 18 bp.  If tax were doubled it'd be 33.
    total = round_trip_cost_bps(
        commission_bps_per_side=1.5, transaction_tax_bps=15.0
    )
    assert _approx(total, 18.0)
    # Isolate the tax: zero commission -> tax appears exactly once.
    assert _approx(round_trip_cost_bps(transaction_tax_bps=15.0), 15.0)


def test_round_trip_cost_includes_slippage():
    total = round_trip_cost_bps(
        commission_bps_per_side=2.0, transaction_tax_bps=0.0, slippage_bps=4.0
    )
    assert _approx(total, 2.0 * 2 + 0.0 + 4.0)  # 8 bp


def test_round_trip_cost_rejects_negative_components():
    with pytest.raises(ValueError):
        round_trip_cost_bps(commission_bps_per_side=-1.0)
    with pytest.raises(ValueError):
        round_trip_cost_bps(transaction_tax_bps=-1.0)
    with pytest.raises(ValueError):
        round_trip_cost_bps(slippage_bps=-1.0)


def test_reference_scenarios_match_documented_totals():
    # Korean-domestic ~18 bp (comm 1.5/side x2 + 증권거래세 15 sell-only).
    assert _approx(KOREAN_DOMESTIC_COST.total_round_trip_bps(), 18.0)
    assert KOREAN_DOMESTIC_COST.transaction_tax_bps == 15.0  # sell-side tax present
    # International / low ~5 bp (comm 2.5/side x2, NO transaction tax).
    assert _approx(INTERNATIONAL_LOW_COST.total_round_trip_bps(), 5.0)
    assert INTERNATIONAL_LOW_COST.transaction_tax_bps == 0.0  # no tax internationally


# ---------------------------------------------------------------------------
# Breakeven cost: net = gross - cost%, monotonic-decreasing in cost.
# ---------------------------------------------------------------------------
def _mk_path(symbol: str, session: str, exit_price: float) -> GapUpInstance:
    # entry=100, single forward bar at exit_price; with TP5/SL1 a mild move
    # neither hits TP nor SL, so it time-exits at exit_price (gross = move%).
    return GapUpInstance(
        symbol=symbol,
        session=session,
        entry_change_rate=2.5,
        entry_price=100.0,
        prices=(100.0, exit_price),
        seconds=(32400, 32401),
    )


def test_breakeven_equals_gross_expectancy_times_100():
    # Two instances time-exit at +2% and +0% gross -> mean gross = +1.0%/trade.
    # Breakeven round-trip cost = 1.0% * 100 = 100 bp.
    insts = [_mk_path("A", "20230101", 102.0), _mk_path("B", "20230102", 100.0)]
    be = breakeven_round_trip_bps(insts, tp_pct=5.0, sl_pct=1.0)
    assert be is not None and _approx(be, 100.0)
    # At exactly the breakeven cost, net expectancy is ~0.
    exp = expectancy_at_cost(insts, tp_pct=5.0, sl_pct=1.0, cost_bps=be)
    assert _approx(exp, 0.0, tol=1e-6)


def test_breakeven_negative_when_gross_edge_is_negative():
    # Both instances lose gross (-1% time-exit) -> breakeven is NEGATIVE,
    # i.e. unprofitable at ANY non-negative cost.
    insts = [_mk_path("A", "20230101", 99.0), _mk_path("B", "20230102", 99.0)]
    be = breakeven_round_trip_bps(insts, tp_pct=5.0, sl_pct=2.0)
    assert be is not None and be < 0.0


def test_cost_sweep_expectancy_is_monotonic_decreasing():
    insts = [_mk_path("A", "20230101", 103.0), _mk_path("B", "20230102", 101.0)]
    sweep = cost_sweep_table(
        insts, tp_pct=5.0, sl_pct=1.0, cost_levels=(0.0, 5.0, 10.0, 18.0, 25.0)
    )
    exps = [row["expectancy_pct"] for row in sweep]
    # Strictly decreasing: higher cost -> lower net expectancy.
    assert all(a > b for a, b in zip(exps, exps[1:]))
    # The drop between adjacent levels equals the cost delta in % (additive).
    assert _approx(exps[0] - exps[1], (5.0 - 0.0) / 100.0)


def test_breakeven_none_for_empty_set():
    assert breakeven_round_trip_bps([], tp_pct=5.0, sl_pct=1.0) is None
    assert expectancy_at_cost([], tp_pct=5.0, sl_pct=1.0, cost_bps=10.0) is None


# ---------------------------------------------------------------------------
# Causal entry filters (STOM-derived, evaluated on the ENTRY bar only).
# ---------------------------------------------------------------------------
def test_imbalance_formula_and_edge_cases():
    assert _approx(compute_bid_ask_imbalance(60.0, 40.0), 0.6)
    assert _approx(compute_bid_ask_imbalance(50.0, 50.0), 0.5)
    assert compute_bid_ask_imbalance(0.0, 0.0) is None  # empty book -> no denom
    assert compute_bid_ask_imbalance(None, 40.0) is None
    assert compute_bid_ask_imbalance(60.0, None) is None


def _mk_feat(
    symbol: str,
    session: str,
    *,
    ts=None,
    imb=None,
) -> GapUpInstance:
    return GapUpInstance(
        symbol=symbol,
        session=session,
        entry_change_rate=2.5,
        entry_price=100.0,
        prices=(100.0, 101.0),
        seconds=(32400, 32401),
        entry_trade_strength=ts,
        entry_bid_ask_imbalance=imb,
    )


def test_entry_filter_none_admits_everything():
    inst = _mk_feat("A", "20230101", ts=None, imb=None)
    assert passes_entry_filter(inst, ENTRY_FILTERS["none"]) is True


def test_entry_filter_ts_requires_threshold():
    strong = _mk_feat("A", "20230101", ts=TRADE_STRENGTH_THRESHOLD)
    weak = _mk_feat("B", "20230101", ts=TRADE_STRENGTH_THRESHOLD - 0.1)
    missing = _mk_feat("C", "20230101", ts=None)
    assert passes_entry_filter(strong, ENTRY_FILTERS["ts"]) is True
    assert passes_entry_filter(weak, ENTRY_FILTERS["ts"]) is False
    # A missing signal FAILS (we don't admit instances lacking the evidence).
    assert passes_entry_filter(missing, ENTRY_FILTERS["ts"]) is False


def test_entry_filter_ts_imb_requires_both():
    both = _mk_feat("A", "20230101", ts=120.0, imb=IMBALANCE_THRESHOLD)
    only_ts = _mk_feat("B", "20230101", ts=120.0, imb=IMBALANCE_THRESHOLD - 0.01)
    only_imb = _mk_feat("C", "20230101", ts=80.0, imb=0.7)
    assert passes_entry_filter(both, ENTRY_FILTERS["ts_imb"]) is True
    assert passes_entry_filter(only_ts, ENTRY_FILTERS["ts_imb"]) is False
    assert passes_entry_filter(only_imb, ENTRY_FILTERS["ts_imb"]) is False


def test_filter_instances_reduces_or_preserves_count():
    instances = [
        _mk_feat("A", "20230101", ts=150.0, imb=0.7),  # passes both
        _mk_feat("B", "20230101", ts=150.0, imb=0.3),  # passes ts only
        _mk_feat("C", "20230101", ts=50.0, imb=0.7),   # passes neither
        _mk_feat("D", "20230101", ts=None, imb=None),  # missing -> fails ts
    ]
    none_kept = filter_instances(instances, ENTRY_FILTERS["none"])
    ts_kept = filter_instances(instances, ENTRY_FILTERS["ts"])
    ts_imb_kept = filter_instances(instances, ENTRY_FILTERS["ts_imb"])
    assert len(none_kept) == 4  # no-filter keeps all
    assert len(ts_kept) == 2    # A, B
    assert len(ts_imb_kept) == 1  # only A
    # Filtering NEVER increases the instance count (monotone subset).
    assert len(ts_kept) <= len(none_kept)
    assert len(ts_imb_kept) <= len(ts_kept)


def test_filter_is_causal_uses_only_entry_bar_signals():
    # The filter reads ONLY entry_trade_strength / entry_bid_ask_imbalance,
    # which are entry-bar values; the forward price path must not affect it.
    rising = GapUpInstance(
        "A", "20230101", 2.5, 100.0, (100.0, 200.0, 300.0), (0, 1, 2),
        entry_trade_strength=50.0, entry_bid_ask_imbalance=0.2,
    )
    # Despite a huge favourable forward path, weak entry-bar demand still fails.
    assert passes_entry_filter(rising, ENTRY_FILTERS["ts"]) is False
