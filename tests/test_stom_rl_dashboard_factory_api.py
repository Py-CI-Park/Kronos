"""Tests for the read-only factory dashboard helpers and routes.

Fixtures pin the 23bp round-trip cost assumption; nothing here asserts profit
or live readiness — only that read-only evidence is served safely.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl.factory.experiment_queue import enqueue_experiment  # noqa: E402
from stom_rl.factory.run_registry import init_registry  # noqa: E402
from webui import rl_dashboard_factory as factory  # noqa: E402
from webui.app import app as flask_app  # noqa: E402


def _write_lane_run(
    root: Path,
    run_name: str,
    *,
    verdict: str = "NO-GO_BASELINE",
    brier: float = 0.21,
    oos_take_count: int = 14,
    mtime: float | None = None,
) -> Path:
    run_dir = root / run_name
    run_dir.mkdir(parents=True)
    summary = {
        "run_id": run_name,
        "verdict": verdict,
        "oos_take_count": oos_take_count,
        "brier": brier,
        "cost_note": "net pct at 23bp round-trip cost",
        "fill_mode": "realized_full",
        "cost_bps": 23.0,
        "split": {"split_hash": "abc123"},
        "parent_run": "parent_lane",
        "aggregate": {
            "oos_take_count": oos_take_count,
            "oos_take_mean_net_pct": 0.91,
            "take_all_mean_net_pct": 0.72,
            "ts_imb_mean_net_pct": 0.72,
            "brier": brier,
        },
    }
    summary_path = run_dir / "probability_lane_summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    calibration = {
        "brier": brier,
        "brier_constant": 0.25,
        "folds": [{"fold_id": 0, "brier": brier, "reliability_bins": [[0.1, 0.05, 20]]}],
    }
    (run_dir / "calibration.json").write_text(json.dumps(calibration), encoding="utf-8")
    ledger = {
        "breakeven_note": "breakeven win probability stated at 23bp round-trip cost",
        "rows": [
            {"symbol": "000250", "session": "2026-06-10", "p_win": 0.62,
             "edge_pct": 0.30, "decision": "TAKE", "net_pct_23bp": 0.40},
            {"symbol": "035720", "session": "2026-06-10", "p_win": 0.55,
             "edge_pct": 0.10, "decision": "TAKE", "net_pct_23bp": 0.20},
            {"symbol": "068270", "session": "2026-06-11", "p_win": 0.41,
             "edge_pct": -0.20, "decision": "SKIP", "net_pct_23bp": -0.30},
        ],
    }
    (run_dir / "edge_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    if mtime is not None:
        os.utime(summary_path, (mtime, mtime))
    return run_dir


def _write_sizing_run(root: Path, run_name: str, *, mtime: float | None = None) -> Path:
    run_dir = root / run_name
    run_dir.mkdir(parents=True)
    summary = {
        "artifact_type": "stacked_sizing_risk_lab",
        "input_kind": "probability_lane_edge_ledger",
        "strategy_label": "stacked supervised gate TAKE - operations design, NOT RL",
        "baseline_label": "same-fill ts_imb RULE baseline",
        "guardrail": "Research-only sizing/risk evidence; not RL, not live-ready, no broker/orders, no profit claim.",
        "cost_note": "net_pct_23bp read directly from probability-lane edge ledger",
        "comparison": {
            "basis_fraction": 0.5,
            "strategy_total_pct": 10.0,
            "baseline_total_pct": 12.0,
            "total_pct_delta": -2.0,
            "strategy_max_drawdown_pct": 5.0,
            "baseline_max_drawdown_pct": 4.0,
            "max_drawdown_delta": 1.0,
            "strategy_risk_adjusted_mean_over_std": 0.3,
            "baseline_risk_adjusted_mean_over_std": 0.2,
            "risk_adjusted_improvement": True,
            "drawdown_improvement": False,
        },
        "strategy": {
            "n_trades": 3,
            "n_sessions": 2,
            "fixed_fraction": {"0.5": {"mean_trade_pct": 0.40}},
            "capacity_cap": {"trades_skipped_capacity": 1},
            "daily_halt": {"5.0": {"total_pct": 9.5, "sessions_halted": 1}},
            "worst_session": {"net_pct": -3.0},
        },
        "baseline": {
            "n_trades": 4,
            "n_sessions": 2,
            "fixed_fraction": {"0.5": {"mean_trade_pct": 0.30}},
            "capacity_cap": {"trades_skipped_capacity": 2},
            "daily_halt": {"5.0": {"total_pct": 11.5, "sessions_halted": 2}},
            "worst_session": {"net_pct": -4.0},
        },
        "p5_prerequisite": {
            "account_level_risk_adjusted_improvement": False,
            "note": "P5 also requires P1/P3; this field only covers P2.",
        },
    }
    summary_path = run_dir / "sizing_summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    if mtime is not None:
        os.utime(summary_path, (mtime, mtime))
    return run_dir


def _write_risk_policy_run(
    root: Path,
    run_name: str,
    *,
    fill_mode: str = "realized_full",
    candidate_pass: bool = True,
    unlocked: bool = False,
    mtime: float | None = None,
) -> Path:
    run_dir = root / run_name
    run_dir.mkdir(parents=True)
    summary = {
        "artifact_type": "risk_policy_lab",
        "run_id": run_name,
        "fill_mode": fill_mode,
        "input_kind": "probability_lane_edge_ledger",
        "edge_ledger_path": f"webui/rl_runs/probability_lane/{run_name}/edge_ledger.json",
        "strategy_label": "stacked supervised gate risk policy - operations design, NOT RL",
        "baseline_label": "same-fill ts_imb RULE baseline",
        "guardrail": "Research-only risk-policy gate; no broker/orders, no live-readiness, no profit claim. ts_imb remains a RULE baseline.",
        "cost_bps": 23.0,
        "basis_fraction": 0.5,
        "selection_bias_note": "chosen after full OOS review; hypothesis generation only",
        "baseline": {
            "total_pct": 100.0,
            "max_drawdown_pct": 10.0,
            "risk_adjusted_mean_over_std": 0.2,
            "n_trades": 4,
            "n_sessions": 2,
        },
        "best": {
            "policy": {
                "policy_id": "pwin_gt_040_size_050_100_halt_25",
                "description": "p_win bucket with causal per-session halt",
                "total_pct": 120.0,
                "max_drawdown_pct": 8.0,
                "risk_adjusted_mean_over_std": 0.5,
                "n_trades": 3,
                "n_sessions": 2,
                "source_take_count": 4,
                "selected_before_halt": 3,
                "trades_skipped_filter": 1,
                "trades_skipped_halt": 0,
                "sessions_halted": 1,
                "mean_size_before_halt": 0.75,
            },
            "comparison": {
                "total_pct_delta": 20.0,
                "max_drawdown_delta": -2.0,
                "risk_adjusted_delta": 0.3,
                "risk_adjusted_improvement": True,
                "drawdown_improvement": True,
                "total_noninferior": True,
                "p2_candidate_pass": candidate_pass,
            },
        },
        "gate": {
            "verdict": "P2_RISK_POLICY_CANDIDATE" if candidate_pass else "P2_RISK_POLICY_NO_GO",
            "best_policy_id": "pwin_gt_040_size_050_100_halt_25",
            "candidate_p2_pass": candidate_pass,
            "implementation_unlocked": unlocked,
            "unlock_note": "fresh OOS/forward required before RL implementation unlock",
        },
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    if mtime is not None:
        os.utime(summary_path, (mtime, mtime))
    return run_dir


def _write_fresh_validation_run(
    root: Path,
    run_name: str,
    *,
    fill_mode: str = "realized_full",
    scope: str = "fresh_forward",
    fresh_pass: bool = True,
    unlocked: bool = True,
    mtime: float | None = None,
) -> Path:
    run_dir = root / run_name
    run_dir.mkdir(parents=True)
    summary = {
        "artifact_type": "frozen_policy_fresh_validation",
        "schema_version": 1,
        "run_id": run_name,
        "fill_mode": fill_mode,
        "validation_scope": scope,
        "is_fresh_validation": scope in {"fresh_oos", "fresh_forward"},
        "source_path": "webui/rl_runs/forward_ledger/example/ledger.jsonl",
        "strategy_label": "frozen deterministic risk policy validation - NOT RL",
        "baseline_label": "same-fill ts_imb RULE baseline",
        "guardrail": "Research-only frozen policy validation; no profit claim, no live-readiness, no broker/orders.",
        "cost_bps": 23.0,
        "selection_bias_guardrail": "Frozen parameters only; no threshold search.",
        "baseline": {
            "total_pct": 100.0,
            "max_drawdown_pct": 10.0,
            "risk_adjusted_mean_over_std": 0.2,
            "n_trades": 4,
            "n_sessions": 2,
        },
        "policy": {
            "policy_id": "pwin_gt_040_size_050_100_halt_25",
            "total_pct": 130.0,
            "max_drawdown_pct": 7.0,
            "risk_adjusted_mean_over_std": 0.6,
            "n_trades": 3,
            "n_sessions": 2,
            "selected_before_halt": 3,
            "sessions_halted": 1,
        },
        "comparison": {
            "total_pct_delta": 30.0,
            "max_drawdown_delta": -3.0,
            "risk_adjusted_delta": 0.4,
            "risk_adjusted_improvement": True,
            "drawdown_improvement": True,
            "total_noninferior": True,
            "enough_trades": True,
            "fresh_gate_pass": fresh_pass,
        },
        "gate": {
            "verdict": "FRESH_VALIDATION_PASS" if fresh_pass else "FRESH_VALIDATION_FAIL",
            "fresh_validation_pass": fresh_pass,
            "implementation_unlocked": unlocked,
            "unlock_note": "fresh validation pass fixture",
            "min_total_delta_pct": 0.0,
            "min_trades": 1,
        },
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    if mtime is not None:
        os.utime(summary_path, (mtime, mtime))
    return run_dir

def test_load_factory_queue_does_not_initialize_empty_registry(tmp_path):
    registry = tmp_path / "factory_registry.sqlite"
    with sqlite3.connect(registry) as conn:
        conn.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")

    payload = factory.load_factory_queue(registry)

    assert payload["available"] is False
    assert payload["reason"] == "registry_table_not_found"
    with sqlite3.connect(registry) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
    assert "runs" not in tables
    assert tables == {"unrelated"}

def _write_forward_ledger_run(root: Path, run_name: str) -> Path:
    run_dir = root / run_name
    run_dir.mkdir(parents=True)
    rows = [
        {
            "schema_version": 1,
            "record_id": f"{run_name}:20260610:000250",
            "recorded_at_utc": "2026-06-11T00:00:00+00:00",
            "session": "20260610",
            "code": "000250",
            "run_id": run_name,
            "model_version": f"{run_name}@summary",
            "p_win": 0.62,
            "edge_pct": 0.3,
            "decision": "TAKE",
            "fill_assumption": "realized_full",
            "realized_outcome_pct": 1.2,
            "baseline_outcome_pct": 1.2,
            "outcome_status": "resolved",
            "cost_bps": 23.0,
        },
        {
            "schema_version": 1,
            "record_id": f"{run_name}:20260611:035720",
            "recorded_at_utc": "2026-06-11T00:00:00+00:00",
            "session": "20260611",
            "code": "035720",
            "run_id": run_name,
            "model_version": f"{run_name}@summary",
            "p_win": 0.49,
            "edge_pct": -0.1,
            "decision": "SKIP",
            "fill_assumption": "realized_full",
            "realized_outcome_pct": None,
            "baseline_outcome_pct": None,
            "outcome_status": "pending",
            "cost_bps": 23.0,
        },
    ]
    (run_dir / "ledger.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    summary = {
        "run_id": run_name,
        "model_version": f"{run_name}@summary",
        "fill_assumption": "realized_full",
        "cost_bps": 23.0,
        "schema_version": 1,
        "total_count": 2,
        "status_counts": {"resolved": 1, "pending": 1},
        "duplicate_policy": "skip_existing_record_id",
        "skipped_duplicate_count": 0,
        "include_outcomes": True,
        "source_edge_ledger_path": "webui/rl_runs/probability_lane/example/edge_ledger.json",
        "output_root": "webui/rl_runs/forward_ledger",
        "guardrail": "Read-only forward/paper evidence ledger; no orders, no broker integration, no live-readiness or profit claim.",
    }
    (run_dir / "ledger.summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return run_dir


def _make_registry(tmp_path: Path) -> Path:
    registry = tmp_path / "factory_registry.sqlite"
    init_registry(registry)
    prereg = tmp_path / "prereg_probability_lane_2026_06_11.md"
    prereg.write_text("# prereg\ncost 23bp round-trip\n", encoding="utf-8")
    enqueue_experiment(
        registry,
        run_id="probability_lane_tp5sl1_2026_06_11",
        split_hash="splithash01",
        cost_bps=23.0,
        seed=42,
        stage="smoke",
        prereg_doc=prereg.name,
        repo_root=tmp_path,
    )
    return registry


@pytest.mark.parametrize(
    "bad_name",
    ["..", "a/b", "a\\b", "../escape", ".", ""],
)
def test_safe_run_dir_rejects_traversal(tmp_path, bad_name):
    with pytest.raises(ValueError):
        factory._safe_run_dir(bad_name, tmp_path)


def test_safe_run_dir_rejects_absolute_path(tmp_path):
    with pytest.raises(ValueError):
        factory._safe_run_dir(str(tmp_path / "outside"), tmp_path / "lane_root")


def test_load_factory_queue_missing_registry(tmp_path):
    payload = factory.load_factory_queue(tmp_path / "absent.sqlite")
    assert payload["available"] is False
    assert payload["reason"] == "registry_not_found"
    assert not (tmp_path / "absent.sqlite").exists()  # read-only: no file created


def test_load_factory_queue_counts(tmp_path):
    registry = _make_registry(tmp_path)
    payload = factory.load_factory_queue(registry)
    assert payload["available"] is True
    assert payload["counts_by_status"]["queued"] == 1
    assert payload["counts_by_status"]["done"] == 0
    runs = payload["latest_runs"]
    assert runs[0]["run_id"] == "probability_lane_tp5sl1_2026_06_11"
    assert runs[0]["cost_bps"] == 23.0
    assert "no profit claim" in payload["guardrail"].lower() or "no profit" in payload["guardrail"].lower()
    assert "read-only" in payload["read_only_dashboard_note"].lower()


def test_load_lane_calibration_roundtrip(tmp_path):
    _write_lane_run(tmp_path, "lane_run_a")
    payload = factory.load_lane_calibration("lane_run_a", root=tmp_path)
    assert payload["available"] is True
    assert payload["run"] == "lane_run_a"
    assert payload["brier"] == 0.21
    assert payload["brier_constant"] == 0.25
    assert payload["folds"][0]["fold_id"] == 0

    missing = factory.load_lane_calibration("lane_run_missing", root=tmp_path)
    assert missing["available"] is False
    assert missing["reason"] == "calibration_not_found"


def test_load_lane_edge_ledger_summary_and_filters(tmp_path):
    _write_lane_run(tmp_path, "lane_run_a")

    payload = factory.load_lane_edge_ledger("lane_run_a", root=tmp_path)
    summary = payload["summary"]
    assert payload["available"] is True
    assert summary["total_rows"] == 3
    assert summary["take_count"] == 2
    assert summary["skip_count"] == 1
    assert summary["take_mean_net_pct"] == pytest.approx(0.30)
    assert summary["skip_mean_net_pct"] == pytest.approx(-0.30)
    assert summary["mean_edge_pct"] == pytest.approx(0.2 / 3, abs=1e-6)
    assert "23bp" in summary["breakeven_note"]
    assert "23bp" in summary["cost_note"]
    assert "23bp" in payload["guardrail"]
    # symbol codes stay strings with leading zeros
    assert payload["rows"][0]["symbol"] == "000250"

    # limit clamp
    limited = factory.load_lane_edge_ledger("lane_run_a", root=tmp_path, limit=2)
    assert len(limited["rows"]) == 2
    assert limited["returned_rows"] == 2
    assert limited["summary"]["total_rows"] == 3  # summary stays full-ledger
    zero = factory.load_lane_edge_ledger("lane_run_a", root=tmp_path, limit=-5)
    assert zero["rows"] == []
    huge = factory.load_lane_edge_ledger("lane_run_a", root=tmp_path, limit=999999)
    assert len(huge["rows"]) == 3

    # decision filter
    takes = factory.load_lane_edge_ledger("lane_run_a", root=tmp_path, decision="TAKE")
    assert {row["decision"] for row in takes["rows"]} == {"TAKE"}
    assert len(takes["rows"]) == 2
    skips = factory.load_lane_edge_ledger("lane_run_a", root=tmp_path, decision="skip")
    assert {row["decision"] for row in skips["rows"]} == {"SKIP"}
    with pytest.raises(ValueError):
        factory.load_lane_edge_ledger("lane_run_a", root=tmp_path, decision="HOLD")


def test_load_lane_edge_ledger_missing(tmp_path):
    (tmp_path / "empty_run").mkdir()
    payload = factory.load_lane_edge_ledger("empty_run", root=tmp_path)
    assert payload["available"] is False
    assert payload["reason"] == "edge_ledger_not_found"


def test_list_lane_runs_ordering_and_fields(tmp_path):
    _write_lane_run(tmp_path, "lane_old", verdict="NO-GO_BASELINE", brier=0.24,
                    oos_take_count=8, mtime=1_700_000_000.0)
    _write_lane_run(tmp_path, "lane_new", verdict="NO-GO_BASELINE", brier=0.21,
                    oos_take_count=14, mtime=1_700_100_000.0)
    (tmp_path / "not_a_lane_run").mkdir()  # no summary file -> skipped

    runs = factory.list_lane_runs(tmp_path)
    assert [run["run"] for run in runs] == ["lane_new", "lane_old"]
    assert runs[0]["verdict"] == "NO-GO_BASELINE"
    assert runs[0]["oos_take_count"] == 14
    assert runs[0]["brier"] == 0.21
    assert runs[0]["fill_mode"] == "realized_full"
    assert runs[0]["cost_bps"] == 23.0
    assert runs[0]["split_hash"] == "abc123"
    assert runs[0]["parent_run"] == "parent_lane"
    assert runs[0]["oos_take_mean_net_pct"] == 0.91
    assert runs[1]["brier"] == 0.24

    assert factory.list_lane_runs(tmp_path / "does_not_exist") == []


def test_list_sizing_runs_exposes_risk_and_p5_block(tmp_path):
    _write_sizing_run(tmp_path, "probability_lane_stacked_realized_full_2026_06_11")

    runs = factory.list_sizing_runs(tmp_path)

    assert runs[0]["fill_mode"] == "realized_full"
    assert runs[0]["strategy_trade_count"] == 3
    assert runs[0]["baseline_trade_count"] == 4
    assert runs[0]["total_pct_delta"] == -2.0
    assert runs[0]["max_drawdown_delta"] == 1.0
    assert runs[0]["mean_trade_delta_pct"] == pytest.approx(0.10)
    assert runs[0]["p5_status"] == "P5_BLOCKED_BY_P2"
    assert "not live-ready" in runs[0]["guardrail"]


def test_list_risk_policy_runs_exposes_candidate_lock(tmp_path):
    _write_risk_policy_run(
        tmp_path,
        "risk_policy_realized_full_2026_06_11",
        fill_mode="realized_full",
    )

    runs = factory.list_risk_policy_runs(tmp_path)

    assert runs[0]["fill_mode"] == "realized_full"
    assert runs[0]["best_policy_id"] == "pwin_gt_040_size_050_100_halt_25"
    assert runs[0]["candidate_p2_pass"] is True
    assert runs[0]["implementation_unlocked"] is False
    assert runs[0]["total_pct_delta"] == 20.0
    assert runs[0]["max_drawdown_delta"] == -2.0
    assert runs[0]["risk_adjusted_delta"] == 0.3
    assert "NOT RL" in runs[0]["strategy_label"]
    assert "RULE baseline" in runs[0]["baseline_label"]


def test_list_fresh_validation_runs_exposes_unlock_gate(tmp_path):
    _write_fresh_validation_run(
        tmp_path,
        "frozen_policy_fresh_realized_full_2026_06_11",
        fill_mode="realized_full",
    )

    runs = factory.list_fresh_validation_runs(tmp_path)

    assert runs[0]["fill_mode"] == "realized_full"
    assert runs[0]["validation_scope"] == "fresh_forward"
    assert runs[0]["policy_id"] == "pwin_gt_040_size_050_100_halt_25"
    assert runs[0]["fresh_validation_pass"] is True
    assert runs[0]["implementation_unlocked"] is True
    assert runs[0]["total_pct_delta"] == 30.0
    assert runs[0]["max_drawdown_delta"] == -3.0
    assert "NOT RL" in runs[0]["strategy_label"]
    assert "RULE baseline" in runs[0]["baseline_label"]


def test_model_build_readiness_keeps_rl_locked_until_fresh_validation(tmp_path):
    risk_root = tmp_path / "risk_policy_lab"
    sizing_root = tmp_path / "sizing_lab"
    forward_root = tmp_path / "forward_ledger"
    _write_risk_policy_run(risk_root, "risk_policy_realized_full_2026_06_11", fill_mode="realized_full")
    _write_risk_policy_run(risk_root, "risk_policy_slgap_full_2026_06_11", fill_mode="slgap_full")
    _write_sizing_run(sizing_root, "probability_lane_stacked_realized_full_2026_06_11")
    _write_forward_ledger_run(forward_root, "probability_lane_stacked_realized_full_2026_06_11")

    payload = factory.load_model_build_readiness(
        risk_root=risk_root,
        sizing_root=sizing_root,
        forward_root=forward_root,
    )

    assert payload["status"] == "MODEL_BUILD_CANDIDATE_NEEDS_FRESH_VALIDATION"
    assert payload["p1_status"] == "PASS"
    assert payload["original_p2_status"] == "FAIL"
    assert payload["risk_policy_status"] == "CANDIDATE_PASS"
    assert payload["fresh_validation_status"] == "FRESH_VALIDATION_REQUIRED"
    assert payload["restricted_rl_status"] == "LOCKED_FRESH_OOS_FORWARD_REQUIRED"
    assert payload["implementation_unlocked"] is False
    assert payload["selected_policy_ids"] == ["pwin_gt_040_size_050_100_halt_25"]
    assert any(step["id"] == "RL-implementation" for step in payload["readiness_steps"])
    assert "hypothesis generation" in payload["selection_bias_note"]


def test_model_build_readiness_unlocks_only_after_both_fresh_fill_modes_pass(tmp_path):
    risk_root = tmp_path / "risk_policy_lab"
    sizing_root = tmp_path / "sizing_lab"
    forward_root = tmp_path / "forward_ledger"
    fresh_root = tmp_path / "fresh_policy_validation"
    _write_risk_policy_run(risk_root, "risk_policy_realized_full_2026_06_11", fill_mode="realized_full")
    _write_risk_policy_run(risk_root, "risk_policy_slgap_full_2026_06_11", fill_mode="slgap_full")
    _write_sizing_run(sizing_root, "probability_lane_stacked_realized_full_2026_06_11")
    _write_forward_ledger_run(forward_root, "probability_lane_stacked_realized_full_2026_06_11")
    _write_fresh_validation_run(fresh_root, "frozen_policy_fresh_realized_full_2026_06_11", fill_mode="realized_full")
    _write_fresh_validation_run(fresh_root, "frozen_policy_fresh_slgap_full_2026_06_11", fill_mode="slgap_full")

    payload = factory.load_model_build_readiness(
        risk_root=risk_root,
        sizing_root=sizing_root,
        forward_root=forward_root,
        fresh_root=fresh_root,
    )

    assert payload["status"] == "MODEL_BUILD_READY_FOR_RESTRICTED_RL"
    assert payload["fresh_validation_status"] == "FRESH_VALIDATION_PASS"
    assert payload["restricted_rl_status"] == "READY_FOR_RESTRICTED_RL_IMPLEMENTATION"
    assert payload["implementation_unlocked"] is True
    assert {run["fill_mode"] for run in payload["fresh_validation_runs"]} == {"realized_full", "slgap_full"}


def test_forward_ledger_runs_and_rows_are_read_only_and_filterable(tmp_path):
    _write_forward_ledger_run(tmp_path, "probability_lane_stacked_realized_full_2026_06_11")

    runs = factory.list_forward_ledger_runs(tmp_path)
    assert runs[0]["total_count"] == 2
    assert runs[0]["resolved_count"] == 1
    assert runs[0]["pending_count"] == 1
    assert runs[0]["duplicate_policy"] == "skip_existing_record_id"
    assert "no orders" in runs[0]["guardrail"]

    payload = factory.load_forward_ledger(
        "probability_lane_stacked_realized_full_2026_06_11",
        root=tmp_path,
        status="resolved",
    )
    assert payload["available"] is True
    assert payload["summary"]["schema_version"] == 1
    assert payload["summary"]["pending_count"] == 1
    assert payload["summary"]["resolved_count"] == 1
    assert payload["rows"][0]["code"] == "000250"

    pending = factory.load_forward_ledger(
        "probability_lane_stacked_realized_full_2026_06_11",
        root=tmp_path,
        status="pending",
    )
    assert pending["rows"][0]["outcome_status"] == "pending"
    with pytest.raises(ValueError):
        factory.load_forward_ledger("probability_lane_stacked_realized_full_2026_06_11", root=tmp_path, status="bad")


def test_flask_factory_routes_smoke(tmp_path, monkeypatch):
    lane_root = tmp_path / "probability_lane"
    _write_lane_run(lane_root, "lane_run_a")
    registry = _make_registry(tmp_path)
    sizing_root = tmp_path / "sizing_lab"
    forward_root = tmp_path / "forward_ledger"
    _write_sizing_run(sizing_root, "probability_lane_stacked_realized_full_2026_06_11")
    _write_forward_ledger_run(forward_root, "probability_lane_stacked_realized_full_2026_06_11")
    risk_root = tmp_path / "risk_policy_lab"
    _write_risk_policy_run(risk_root, "risk_policy_realized_full_2026_06_11", fill_mode="realized_full")
    _write_risk_policy_run(risk_root, "risk_policy_slgap_full_2026_06_11", fill_mode="slgap_full")
    fresh_root = tmp_path / "fresh_policy_validation"
    monkeypatch.setattr(factory, "PROBABILITY_LANE_ROOT", lane_root)
    monkeypatch.setattr(factory, "FACTORY_REGISTRY_PATH", registry)
    monkeypatch.setattr(factory, "SIZING_LAB_ROOT", sizing_root)
    monkeypatch.setattr(factory, "FORWARD_LEDGER_ROOT", forward_root)
    monkeypatch.setattr(factory, "RISK_POLICY_ROOT", risk_root)
    monkeypatch.setattr(factory, "FRESH_VALIDATION_ROOT", fresh_root)

    client = flask_app.test_client()

    queue = client.get("/api/rl/factory/queue")
    assert queue.status_code == 200
    assert queue.get_json()["available"] is True
    assert queue.get_json()["counts_by_status"]["queued"] == 1

    lane_runs = client.get("/api/rl/factory/lane-runs")
    assert lane_runs.status_code == 200
    assert lane_runs.get_json()["runs"][0]["run"] == "lane_run_a"

    calibration = client.get("/api/rl/factory/lane/lane_run_a/calibration")
    assert calibration.status_code == 200
    assert calibration.get_json()["brier"] == 0.21

    ledger = client.get("/api/rl/factory/lane/lane_run_a/edge-ledger?limit=1&decision=TAKE")
    assert ledger.status_code == 200
    body = ledger.get_json()
    assert len(body["rows"]) == 1
    assert body["rows"][0]["decision"] == "TAKE"
    assert body["summary"]["take_mean_net_pct"] == pytest.approx(0.30)

    sizing = client.get("/api/rl/factory/sizing-runs")
    assert sizing.status_code == 200
    assert sizing.get_json()["runs"][0]["p5_status"] == "P5_BLOCKED_BY_P2"

    risk_policy = client.get("/api/rl/factory/risk-policy-runs")
    assert risk_policy.status_code == 200
    assert risk_policy.get_json()["runs"][0]["candidate_p2_pass"] is True

    fresh_validation = client.get("/api/rl/factory/fresh-validation-runs")
    assert fresh_validation.status_code == 200
    assert fresh_validation.get_json()["runs"] == []

    readiness = client.get("/api/rl/factory/model-build-readiness")
    assert readiness.status_code == 200
    readiness_payload = readiness.get_json()
    assert readiness_payload["restricted_rl_status"] == "LOCKED_DASHBOARD_RESEARCH_ONLY"
    assert readiness_payload["fresh_validation_status"] == "RESEARCH_ONLY_EVIDENCE_REVIEW"
    assert readiness_payload["implementation_unlocked"] is False
    assert readiness_payload["model_build_allowed"] is False
    assert readiness_payload["research_only_guardrail"]["status"] == "NO-GO"
    assert readiness_payload["research_only_guardrail"]["labels"] == ["NO-GO", "RESEARCH_ONLY", "23bp", "ts_imb RULE baseline"]

    forward_runs = client.get("/api/rl/factory/forward-ledgers")
    assert forward_runs.status_code == 200
    assert forward_runs.get_json()["runs"][0]["resolved_count"] == 1

    forward_rows = client.get("/api/rl/factory/forward-ledger/probability_lane_stacked_realized_full_2026_06_11?limit=1&status=resolved")
    assert forward_rows.status_code == 200
    assert forward_rows.get_json()["rows"][0]["code"] == "000250"

    bad_status = client.get("/api/rl/factory/forward-ledger/probability_lane_stacked_realized_full_2026_06_11?status=bad")
    assert bad_status.status_code == 400
    bad_decision = client.get("/api/rl/factory/lane/lane_run_a/edge-ledger?decision=HOLD")
    assert bad_decision.status_code == 400

    traversal = client.get("/api/rl/factory/lane/..%5Csecret/calibration")
    assert traversal.status_code in {400, 404}
