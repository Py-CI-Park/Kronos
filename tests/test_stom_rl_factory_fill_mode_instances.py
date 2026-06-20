"""Tests for repricing frozen gap-up manifests by fill mode."""

from __future__ import annotations

from stom_rl.factory.fill_mode_instances import build_repriced_row
from stom_rl.gap_up_backtest import GapUpBacktestConfig, GapUpInstance


def test_build_repriced_row_preserves_code_and_adds_fill_metadata() -> None:
    inst = GapUpInstance(
        symbol="000250",
        session="20260102",
        entry_change_rate=3.2,
        entry_price=100.0,
        prices=(100.0, 106.0),
        seconds=(9 * 3600, 9 * 3600 + 1),
        entry_trade_strength=120.0,
        entry_sec_amount=30_000.0,
        entry_bid_ask_imbalance=0.75,
    )

    row = build_repriced_row(
        {"symbol": "000250", "session": "20260102", "split": "out_of_sample"},
        inst,
        config=GapUpBacktestConfig(db_path="unused.db"),
        fill_mode="realized",
        cost_bps=25.0,
    )

    assert row["symbol"] == "000250"
    assert row["fill_mode"] == "realized"
    assert row["source_cost_bps"] == 25.0
    assert row["pass_ts_imb"] is True
    assert row["tp5_sl1_reason"] == "tp"
    assert row["tp5_sl1_net_pct"] == 5.75  # realized TP credits the overshoot minus 25bp


def test_build_repriced_row_sl_gap_stress_keeps_conservative_tp() -> None:
    inst = GapUpInstance(
        symbol="000250",
        session="20260102",
        entry_change_rate=3.2,
        entry_price=100.0,
        prices=(100.0, 106.0),
        seconds=(9 * 3600, 9 * 3600 + 1),
        entry_trade_strength=120.0,
        entry_sec_amount=30_000.0,
        entry_bid_ask_imbalance=0.75,
    )

    row = build_repriced_row(
        {"symbol": "000250", "session": "20260102"},
        inst,
        config=GapUpBacktestConfig(db_path="unused.db"),
        fill_mode="sl_gap_stress",
        cost_bps=25.0,
    )

    assert row["tp5_sl1_reason"] == "tp"
    assert row["tp5_sl1_net_pct"] == 4.75
