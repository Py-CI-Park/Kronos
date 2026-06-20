"""Tests for the probability lane (supervised gate, NOT RL)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from stom_rl.factory.probability_lane import (
    COST_CONVERSION_PCT,
    LaneConfig,
    ProbabilityLaneError,
    evaluate_gates,
    load_candidate_frame,
    run_probability_lane,
)


def _synthetic_instances(n_sessions: int = 14, per_session: int = 30, seed: int = 7) -> list[dict]:
    """Logged-instance rows with a planted signal: high imbalance wins more."""

    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_sessions):
        session = f"2024{1 + s // 28:02d}{1 + s % 28:02d}"
        for i in range(per_session):
            imb = float(rng.uniform(0.0, 1.0))
            win = rng.uniform() < (0.25 + 0.5 * imb)
            net = float(rng.normal(4.0, 0.5)) if win else float(rng.normal(-1.2, 0.2))
            rows.append(
                {
                    "symbol": f"{rng.integers(0, 999999):06d}",
                    "session": session,
                    "entry_change_rate": float(rng.uniform(2.0, 12.0)),
                    "entry_trade_strength": float(rng.uniform(50.0, 400.0)),
                    "entry_bid_ask_imbalance": imb,
                    "entry_sec_amount": float(rng.uniform(10.0, 900.0)),
                    "entry_price": float(rng.uniform(500.0, 50000.0)),
                    "pass_ts_imb": bool(imb >= 0.5),
                    "tp5_sl1_net_pct": net,
                }
            )
    return rows


@pytest.fixture()
def instances_path(tmp_path: Path) -> Path:
    path = tmp_path / "instances.json"
    path.write_text(json.dumps(_synthetic_instances()), encoding="utf-8")
    return path


def test_load_candidate_frame_applies_cost_conversion_and_keeps_codes(instances_path: Path) -> None:
    frame = load_candidate_frame(instances_path)
    assert (frame["net_pct_23bp"] - frame["tp5_sl1_net_pct"]).round(6).eq(COST_CONVERSION_PCT).all()
    assert frame["symbol"].map(lambda s: isinstance(s, str) and len(s) == 6).all()
    assert set(frame["win"].unique()) <= {0, 1}


def test_load_candidate_frame_rejects_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([{"symbol": "000250"}]), encoding="utf-8")
    with pytest.raises(ProbabilityLaneError):
        load_candidate_frame(path)


def _aggregate(**overrides) -> dict:
    base = {
        "oos_take_count": 150,
        "oos_take_mean_net_pct": 1.0,
        "oos_take_total_net_pct": 150.0,
        "take_all_mean_net_pct": 0.2,
        "ts_imb_mean_net_pct": 0.8,
        "ts_imb_count": 60,
        "brier": 0.20,
        "brier_constant": 0.24,
    }
    base.update(overrides)
    return base


def _shuffled_failing() -> dict:
    return _aggregate(oos_take_mean_net_pct=0.1, take_all_mean_net_pct=0.2)


def test_evaluate_gates_go_candidate() -> None:
    result = evaluate_gates(_aggregate(), _shuffled_failing(), [])
    assert result["verdict"] == "GO_CANDIDATE"
    assert result["blocking_reasons"] == []


def test_evaluate_gates_insufficient_take_is_inconclusive() -> None:
    result = evaluate_gates(_aggregate(oos_take_count=6), _shuffled_failing(), [])
    assert result["verdict"] == "INCONCLUSIVE"
    assert "insufficient_oos_take_trades" in result["blocking_reasons"]


def test_evaluate_gates_baseline_failures() -> None:
    result = evaluate_gates(
        _aggregate(oos_take_mean_net_pct=0.1), _shuffled_failing(), []
    )
    assert result["verdict"] == "NO-GO_BASELINE"
    assert "failed_baseline:take_all" in result["blocking_reasons"]
    assert "failed_baseline:ts_imb_rule" in result["blocking_reasons"]


def test_evaluate_gates_shuffled_control_pass_blocks() -> None:
    shuffled_passing = _aggregate()
    result = evaluate_gates(_aggregate(), shuffled_passing, [])
    assert result["verdict"] == "NO-GO_CONTROL"
    assert "failed_controls" in result["blocking_reasons"]


def test_evaluate_gates_calibration_skill() -> None:
    result = evaluate_gates(
        _aggregate(brier=0.30, brier_constant=0.24), _shuffled_failing(), []
    )
    assert result["verdict"] == "NO-GO_CONTROL"
    assert "failed_calibration_skill" in result["blocking_reasons"]


def test_evaluate_gates_ablation_majority_blocks() -> None:
    better = [
        {"oos_take_mean_net_pct": 2.0, "take_all_mean_net_pct": 0.2} for _ in range(3)
    ]
    result = evaluate_gates(_aggregate(), _shuffled_failing(), better)
    assert result["verdict"] == "NO-GO_ABLATION"
    assert "failed_ablations" in result["blocking_reasons"]


def test_run_probability_lane_writes_artifacts_and_verdict(instances_path: Path, tmp_path: Path) -> None:
    config = LaneConfig(
        run_id="lane_smoke",
        instances_path=instances_path,
        output_dir=tmp_path / "runs",
        n_folds=3,
        min_oos_take=10,
        allow_few_folds=True,
    )
    payload = run_probability_lane(config)
    assert payload["verdict"] in {
        "GO_CANDIDATE",
        "NO-GO",
        "NO-GO_BASELINE",
        "NO-GO_CONTROL",
        "NO-GO_ABLATION",
        "INCONCLUSIVE",
    }
    out = tmp_path / "runs" / "lane_smoke"
    summary = json.loads((out / "probability_lane_summary.json").read_text(encoding="utf-8"))
    assert summary["strategy_label"].startswith("supervised gate")
    assert summary["cost_bps"] == 23.0
    assert summary["fill_mode"] == "unknown"
    assert summary["parent_run"] is None
    assert len(summary["ablations"]) == 5
    assert summary["shuffled_label_control"]["oos_take_count"] >= 0
    calibration = json.loads((out / "calibration.json").read_text(encoding="utf-8"))
    assert 0.0 <= calibration["brier"] <= 1.0
    ledger = json.loads((out / "edge_ledger.json").read_text(encoding="utf-8"))
    assert ledger["rows"], "edge ledger must contain per-candidate rows"
    first = ledger["rows"][0]
    assert {"symbol", "session", "p_win", "edge_pct", "decision", "net_pct_23bp"} <= set(first)
    assert first["decision"] in {"TAKE", "SKIP"}


def test_run_probability_lane_deterministic(instances_path: Path, tmp_path: Path) -> None:
    config_a = LaneConfig(
        run_id="lane_a",
        instances_path=instances_path,
        output_dir=tmp_path / "a",
        n_folds=3,
        min_oos_take=10,
        allow_few_folds=True,
    )
    config_b = LaneConfig(
        run_id="lane_b",
        instances_path=instances_path,
        output_dir=tmp_path / "b",
        n_folds=3,
        min_oos_take=10,
        allow_few_folds=True,
    )
    payload_a = run_probability_lane(config_a)
    payload_b = run_probability_lane(config_b)
    assert payload_a["aggregate"] == payload_b["aggregate"]
    assert payload_a["verdict"] == payload_b["verdict"]

# ---------------------------------------------------------------------------
# Stacked / matched modes (docs/stom_probability_lane_stacked_prereg_2026-06-11.md)
# ---------------------------------------------------------------------------

from stom_rl.factory.probability_lane import (  # noqa: E402 - extension imports
    evaluate_matched_gates,
    evaluate_stacked_gates,
)


def _fold_rows(deltas: list[float | None]) -> list[dict]:
    rows = []
    for i, delta in enumerate(deltas):
        rows.append(
            {
                "fold_id": i,
                "take_count": 30,
                "take_mean_net_pct": None if delta is None else 1.0 + delta,
                "take_all_mean_net_pct": 1.0,
            }
        )
    return rows


def test_evaluate_stacked_gates_go_candidate() -> None:
    aggregate = _aggregate(
        oos_take_mean_net_pct=1.1, take_all_mean_net_pct=0.8, ts_imb_mean_net_pct=0.8
    )
    result = evaluate_stacked_gates(
        aggregate,
        _fold_rows([0.1, 0.2, 0.05, -0.1, 0.3]),
        _shuffled_failing(),
        [],
    )
    assert result["verdict"] == "GO_CANDIDATE"
    assert result["consistent_folds"] == 4
    assert result["blocking_reasons"] == []


def test_evaluate_stacked_gates_fold_consistency_blocks() -> None:
    aggregate = _aggregate(
        oos_take_mean_net_pct=1.1, take_all_mean_net_pct=0.8, ts_imb_mean_net_pct=0.8
    )
    result = evaluate_stacked_gates(
        aggregate,
        _fold_rows([0.1, -0.2, None, -0.1, 0.3]),
        _shuffled_failing(),
        [],
    )
    assert result["verdict"] == "NO-GO_BASELINE"
    assert "failed_fold_consistency" in result["blocking_reasons"]
    assert result["consistent_folds"] == 2


def test_evaluate_stacked_gates_shuffled_control_blocks() -> None:
    aggregate = _aggregate(
        oos_take_mean_net_pct=1.1, take_all_mean_net_pct=0.8, ts_imb_mean_net_pct=0.8
    )
    result = evaluate_stacked_gates(
        aggregate,
        _fold_rows([0.1, 0.2, 0.05, 0.1, 0.3]),
        _aggregate(oos_take_mean_net_pct=1.0, take_all_mean_net_pct=0.8),
        [],
    )
    assert result["verdict"] == "NO-GO_CONTROL"
    assert "failed_controls" in result["blocking_reasons"]


def test_evaluate_matched_gates_supporting_labels() -> None:
    passing = _aggregate(
        oos_take_count=150,
        ts_imb_count=140,
        oos_take_mean_net_pct=0.9,
        ts_imb_mean_net_pct=0.8,
    )
    assert evaluate_matched_gates(passing)["verdict"] == "SUPPORTING_PASS"

    count_mismatch = _aggregate(oos_take_count=150, ts_imb_count=400)
    result = evaluate_matched_gates(count_mismatch)
    assert result["verdict"] == "SUPPORTING_FAIL"
    assert "failed_count_match" in result["blocking_reasons"]

    low_power = _aggregate(oos_take_count=10, ts_imb_count=10)
    assert evaluate_matched_gates(low_power)["verdict"] == "INCONCLUSIVE"


def test_run_probability_lane_stacked_mode(instances_path: Path, tmp_path: Path) -> None:
    config = LaneConfig(
        run_id="lane_stacked",
        instances_path=instances_path,
        output_dir=tmp_path / "runs",
        n_folds=3,
        min_oos_take=10,
        allow_few_folds=True,
        mode="stacked_ts_imb",
        prereg_doc="docs/stom_probability_lane_stacked_prereg_2026-06-11.md",
        fill_mode="realized_full",
        parent_run="parent_lane",
    )
    payload = run_probability_lane(config)
    assert payload["mode"] == "stacked_ts_imb"
    assert payload["fill_mode"] == "realized_full"
    assert payload["parent_run"] == "parent_lane"
    assert payload["decision_universe"] == "ts_imb"
    agg = payload["aggregate"]
    # decision universe is the ts_imb subset: takes cannot exceed subset size
    assert agg["oos_take_count"] <= agg["ts_imb_count"]
    assert agg["oos_take_count"] + agg["skipped_count"] == agg["ts_imb_count"]
    # in stacked mode take_all == ts_imb-alone by construction
    assert agg["take_all_mean_net_pct"] == pytest.approx(agg["ts_imb_mean_net_pct"])
    assert "consistent_folds" in payload["gates"]
    assert payload["shuffled_label_control"] is not None
    assert len(payload["ablations"]) == 5


def test_run_probability_lane_matched_mode(instances_path: Path, tmp_path: Path) -> None:
    config = LaneConfig(
        run_id="lane_matched",
        instances_path=instances_path,
        output_dir=tmp_path / "runs",
        n_folds=3,
        min_oos_take=10,
        allow_few_folds=True,
        mode="matched_threshold",
        prereg_doc="docs/stom_probability_lane_stacked_prereg_2026-06-11.md",
    )
    payload = run_probability_lane(config)
    assert payload["mode"] == "matched_threshold"
    assert payload["gates"]["role"] == "supporting_evidence_only"
    assert payload["verdict"] in {"SUPPORTING_PASS", "SUPPORTING_FAIL", "INCONCLUSIVE"}
    # supporting experiment records thresholds and skips controls/ablations
    assert payload["shuffled_label_control"] is None
    assert payload["ablations"] == []
    thresholds = [row["edge_threshold"] for row in payload["fold_thresholds"]]
    assert len(thresholds) == 3


def test_run_probability_lane_split_hash_guard(instances_path: Path, tmp_path: Path) -> None:
    config = LaneConfig(
        run_id="lane_guard",
        instances_path=instances_path,
        output_dir=tmp_path / "runs",
        n_folds=3,
        min_oos_take=10,
        allow_few_folds=True,
        expected_split_hash="deadbeefdeadbeef",
    )
    with pytest.raises(ProbabilityLaneError, match="split hash mismatch"):
        run_probability_lane(config)
