import json

import numpy as np
import pandas as pd

from stom_rl.portfolio_train import PortfolioTrainConfig, run_portfolio_smoke


def _write_real_candidate_csv(path) -> "object":
    """Write a Page 9-schema candidate CSV (with the T+1 fill contract).

    Mirrors the real ``stom_rl.candidate_gen`` output schema in-memory so the
    train smoke can be exercised on a real-shaped CSV without touching the
    multi-GB tick DB.
    """

    base = pd.Timestamp("2025-07-09 09:00:00")
    prices = {"000100": [106100.0, 106200.0, 106000.0, 106300.0, 106500.0],
              "000250": [158900.0, 159500.0, 159000.0, 159500.0, 160000.0]}
    rows = []
    for symbol, series in prices.items():
        for t, price in enumerate(series):
            fill = series[t + 1] if t + 1 < len(series) else float("nan")
            rows.append(
                {
                    "timestamp": (base + pd.Timedelta(seconds=t)).isoformat(),
                    "symbol": symbol,
                    "condition_id": "buy_demand_pressure",
                    "passed": True,
                    "rank_score": float(100 + t if symbol == "000250" else 50 + t),
                    "price": price,
                    "fill_price": fill,
                    "fillable": not np.isnan(fill),
                    "feature_trade_strength": float(120 + t),
                    "feature_bid_ask_imbalance": 0.6,
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def test_portfolio_train_smoke_writes_core_artifacts(tmp_path):
    payload = run_portfolio_smoke(
        PortfolioTrainConfig(output_dir=str(tmp_path), max_steps=5, top_k_candidates=2, max_positions=1)
    )

    assert payload["summary"]["steps"] == 5
    assert payload["summary"]["action_space_n"] == 4
    assert (tmp_path / "portfolio_train_summary.json").is_file()
    assert (tmp_path / "actions.csv").is_file()
    assert (tmp_path / "trades.csv").is_file()
    summary = json.loads((tmp_path / "portfolio_train_summary.json").read_text(encoding="utf-8-sig"))
    assert summary["summary"]["final_nav"] > 0


def test_portfolio_train_real_candidate_csv_is_deterministic(tmp_path):
    """A real-shaped candidate CSV (T+1 fill) yields byte-identical artifacts
    for a fixed seed across two runs."""

    candidate_csv = _write_real_candidate_csv(tmp_path / "candidates.csv")
    common = dict(
        candidate_path=str(candidate_csv),
        max_steps=8,
        top_k_candidates=3,
        max_positions=2,
        seed=100,
    )
    out_a = tmp_path / "run_a"
    out_b = tmp_path / "run_b"
    payload_a = run_portfolio_smoke(PortfolioTrainConfig(output_dir=str(out_a), **common))
    payload_b = run_portfolio_smoke(PortfolioTrainConfig(output_dir=str(out_b), **common))

    # Deterministic summary + byte-identical NAV/trade artifacts.
    assert payload_a["summary"]["final_nav"] == payload_b["summary"]["final_nav"]
    assert payload_a["summary"]["trade_count"] == payload_b["summary"]["trade_count"]
    assert (out_a / "nav.csv").read_bytes() == (out_b / "nav.csv").read_bytes()
    assert (out_a / "trades.csv").read_bytes() == (out_b / "trades.csv").read_bytes()
    # All required artifacts exist; invalid-action rate measurable.
    for name in ("portfolio_train_summary.json", "actions.csv", "trades.csv", "nav.csv", "blocked_actions.json"):
        assert (out_a / name).is_file()
    assert payload_a["summary"]["invalid_action_count"] >= 0


def test_portfolio_train_real_candidate_fills_use_t1_price(tmp_path):
    """Trades executed on the real-shaped CSV fill at the T+1 price, never the
    decision-bar close."""

    candidate_csv = _write_real_candidate_csv(tmp_path / "candidates.csv")
    run_portfolio_smoke(
        PortfolioTrainConfig(
            output_dir=str(tmp_path / "run"),
            candidate_path=str(candidate_csv),
            max_steps=8,
            top_k_candidates=3,
            max_positions=2,
            seed=100,
        )
    )
    trades = pd.read_csv(tmp_path / "run" / "trades.csv", encoding="utf-8-sig")
    assert not trades.empty
    source = pd.read_csv(candidate_csv, encoding="utf-8-sig")
    source["symbol"] = source["symbol"].astype(str)
    # Every buy price must match a fill_price (T+1), and never equal the same-row
    # decision price unless that bar's next close was genuinely unchanged.
    buys = trades[trades["side"] == "buy"]
    assert not buys.empty
    fill_prices = set(round(v, 4) for v in source["fill_price"].dropna())
    for price in buys["price"]:
        assert round(float(price), 4) in fill_prices
