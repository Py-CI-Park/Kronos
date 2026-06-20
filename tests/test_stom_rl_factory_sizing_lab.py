"""Tests for the ts_imb RULE sizing/risk operations lab (RULE track, NOT RL)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from stom_rl.factory.sizing_lab import (
    COST_CONVERSION_PCT,
    SizingLabError,
    daily_loss_halt,
    fixed_fraction_curve,
    load_decision_ledger,
    load_rule_trades,
    run_sizing_lab,
    run_stacked_sizing_lab,
    session_concurrency,
    volatility_targeted_curve,
)


def _synthetic_instances(seed: int = 11) -> list[dict]:
    """~30 logged-instance rows, mixed pass_ts_imb, leading-zero symbol codes."""

    rng = np.random.default_rng(seed)
    rows = []
    sessions = ["20240105", "20240108", "20240109"]
    for s_idx, session in enumerate(sessions):
        for i in range(10):
            rows.append(
                {
                    "symbol": f"{rng.integers(0, 9999):06d}",
                    "session": session,
                    "pass_ts_imb": bool((s_idx + i) % 3 != 0),
                    "tp5_sl1_net_pct": float(rng.normal(0.5, 2.0)),
                }
            )
    rng.shuffle(rows)  # loader must restore chronological order itself
    return rows


@pytest.fixture()
def instances_path(tmp_path: Path) -> Path:
    path = tmp_path / "instances.json"
    path.write_text(json.dumps(_synthetic_instances()), encoding="utf-8")
    return path


def test_load_rule_trades_filters_converts_and_orders(instances_path: Path) -> None:
    frame = load_rule_trades(instances_path)
    raw = json.loads(instances_path.read_text(encoding="utf-8"))
    expected_n = sum(1 for r in raw if r["pass_ts_imb"])
    assert len(frame) == expected_n
    # 25bp cache -> 23bp via +0.02pp.
    assert (frame["net_pct_23bp"] - frame["tp5_sl1_net_pct"]).round(9).eq(
        COST_CONVERSION_PCT
    ).all()
    # Leading-zero codes survive as strings.
    assert frame["symbol"].map(lambda s: isinstance(s, str) and len(s) == 6).all()
    # Chronological (session, symbol) ordering despite shuffled input.
    keys = list(zip(frame["session"], frame["symbol"]))
    assert keys == sorted(keys)


def test_load_rule_trades_rejects_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([{"symbol": "000250"}]), encoding="utf-8")
    with pytest.raises(SizingLabError):
        load_rule_trades(path)


def test_fixed_fraction_curve_hand_computed() -> None:
    # contributions at fraction 0.5: [1.0, -0.5, -0.5, 1.5]
    # cumulative: [1.0, 0.5, 0.0, 1.5] -> total 1.5, MDD 1.0 (peak 1.0 -> trough 0.0)
    result = fixed_fraction_curve([2.0, -1.0, -1.0, 3.0], 0.5)
    assert result["total_pct"] == pytest.approx(1.5)
    assert result["max_drawdown_pct"] == pytest.approx(1.0)
    assert result["longest_losing_streak"] == 2
    assert result["n_trades"] == 4
    assert result["fraction"] == 0.5


def test_fixed_fraction_curve_counts_initial_drawdown() -> None:
    result = fixed_fraction_curve([-2.0, 1.0], 1.0)
    assert result["max_drawdown_pct"] == pytest.approx(2.0)


def test_volatility_target_warmup_uses_max_leverage() -> None:
    # With only 10 trades, no scale can be estimated (min_periods=10 + shift 1),
    # so every trade runs at max_leverage.
    returns = [1.0, -1.0] * 5
    result = volatility_targeted_curve(returns, target_pct=1.0, max_leverage=1.0)
    assert result["mean_scale"] == pytest.approx(1.0)
    assert result["total_pct"] == pytest.approx(sum(returns))


def test_volatility_target_is_causal_no_lookahead() -> None:
    rng = np.random.default_rng(3)
    returns = rng.normal(0.0, 2.0, size=15).tolist()
    base = volatility_targeted_curve(returns, target_pct=1.0, window=50)
    # Changing the LAST trade's return must not change any sizing scale:
    # trade i's scale may only depend on trades strictly before i.
    perturbed = list(returns)
    perturbed[-1] = 50.0
    after = volatility_targeted_curve(perturbed, target_pct=1.0, window=50)
    assert after["mean_scale"] == pytest.approx(base["mean_scale"])


def test_session_concurrency_distribution() -> None:
    import pandas as pd

    frame = pd.DataFrame(
        {
            "session": ["a"] * 3 + ["b"] + ["c"] * 2,
            "net_pct_23bp": [0.1] * 6,
        }
    )
    result = session_concurrency(frame)
    assert result["n_sessions"] == 3
    assert result["max_trades_per_session"] == 3
    assert result["mean_trades_per_session"] == pytest.approx(2.0)
    assert result["p95_trades_per_session"] == pytest.approx(
        float(np.percentile([3, 1, 2], 95))
    )


def test_daily_loss_halt_stops_after_breach() -> None:
    import pandas as pd

    # Session A: -1.5, then -1.0 -> cum -2.5 <= -2.0 halts; +2.0 is skipped.
    # Session B: +1.0, +1.0 -> never halts.
    frame = pd.DataFrame(
        {
            "session": ["20240105"] * 3 + ["20240108"] * 2,
            "net_pct_23bp": [-1.5, -1.0, 2.0, 1.0, 1.0],
        }
    )
    result = daily_loss_halt(frame, halt_loss_pct=2.0)
    assert result["total_pct"] == pytest.approx(-0.5)
    assert result["no_halt_total_pct"] == pytest.approx(1.5)
    assert result["sessions_halted"] == 1
    assert result["trades_taken"] == 4
    assert result["trades_skipped"] == 1


def test_run_sizing_lab_writes_artifact_with_guardrails(
    instances_path: Path, tmp_path: Path
) -> None:
    output = tmp_path / "runs" / "sizing_summary.json"
    payload = run_sizing_lab(instances_path, output)
    assert output.is_file()
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written == payload
    assert written["strategy_label"] == "ts_imb RULE baseline - operations design, NOT RL"
    assert written["cost_note"] == "23bp via +0.02pp conversion from 25bp cache"
    assert "not live-ready" in written["guardrail"]
    assert "not RL" in written["guardrail"]
    assert set(written["fixed_fraction"]) == {"0.25", "0.5", "1.0"}
    assert set(written["daily_halt"]) == {"2.0", "3.0", "5.0"}
    assert written["vol_target"]["target_pct"] == 1.0
    assert written["concurrency"]["max_trades_per_session"] >= 1
    assert written["n_trades"] > 0


def test_load_decision_ledger_filters_and_preserves_codes(tmp_path: Path) -> None:
    ledger_path = tmp_path / "edge_ledger.json"
    ledger_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "symbol": "000250",
                        "session": "20240105",
                        "decision": "SKIP",
                        "net_pct_23bp": -0.2,
                    },
                    {
                        "symbol": "000010",
                        "session": "20240105",
                        "decision": "TAKE",
                        "net_pct_23bp": 1.2,
                    },
                    {
                        "symbol": "035720",
                        "session": "20240108",
                        "decision": "TAKE",
                        "net_pct_23bp": -0.4,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    all_rows = load_decision_ledger(ledger_path)
    take_rows = load_decision_ledger(ledger_path, decision="TAKE")
    assert list(all_rows["symbol"]) == ["000010", "000250", "035720"]
    assert list(take_rows["symbol"]) == ["000010", "035720"]
    assert take_rows["net_pct_23bp"].tolist() == [1.2, -0.4]


def test_run_stacked_sizing_lab_compares_strategy_to_baseline(tmp_path: Path) -> None:
    ledger_path = tmp_path / "edge_ledger.json"
    rows = []
    take_values = [1.0, 0.8, 1.2, 0.9, 1.1, 0.7]
    for i in range(12):
        rows.append(
            {
                "symbol": f"{i:06d}",
                "session": "20240105",
                "decision": "TAKE" if i < 6 else "SKIP",
                "net_pct_23bp": take_values[i] if i < 6 else -0.5,
            }
        )
    ledger_path.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    output = tmp_path / "stacked_sizing.json"

    payload = run_stacked_sizing_lab(ledger_path, output, run_id="lane_run")
    assert output.is_file()
    assert payload["artifact_type"] == "stacked_sizing_risk_lab"
    assert payload["run_id"] == "lane_run"
    assert payload["strategy"]["n_trades"] == 6
    assert payload["baseline"]["n_trades"] == 12
    assert payload["comparison"]["strategy_total_pct"] > payload["comparison"]["baseline_total_pct"]
    assert payload["p5_prerequisite"]["account_level_risk_adjusted_improvement"] is True
    assert "not RL" in payload["guardrail"]
