"""Tests for the frozen risk-policy fresh validation gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stom_rl.factory.frozen_policy_validator import (
    FrozenPolicyConfig,
    FrozenPolicyValidationError,
    load_validation_frame,
    run_frozen_policy_validation,
)


def _edge_ledger(path: Path, *, invalid_decision: bool = False) -> Path:
    rows = [
        {"symbol": "000250", "session": "20260202", "decision": "TAKE", "p_win": 0.62, "edge_pct": 0.8, "net_pct_23bp": 2.0},
        {"symbol": "035720", "session": "20260202", "decision": "TAKE", "p_win": 0.42, "edge_pct": 0.2, "net_pct_23bp": -0.4},
        {"symbol": "068270", "session": "20260202", "decision": "SKIP", "p_win": 0.31, "edge_pct": -0.4, "net_pct_23bp": -4.0},
        {"symbol": "000660", "session": "20260203", "decision": "TAKE", "p_win": 0.58, "edge_pct": 0.7, "net_pct_23bp": 1.5},
        {"symbol": "005930", "session": "20260203", "decision": "SKIP", "p_win": 0.25, "edge_pct": -0.5, "net_pct_23bp": -3.0},
    ]
    if invalid_decision:
        rows[0]["decision"] = "HOLD"
    path.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    return path


def _forward_jsonl(path: Path) -> Path:
    rows = [
        {"code": "000250", "session": "20260202", "decision": "TAKE", "p_win": 0.62, "edge_pct": 0.8, "realized_outcome_pct": 2.0, "baseline_outcome_pct": 2.0},
        {"code": "035720", "session": "20260202", "decision": "TAKE", "p_win": 0.42, "edge_pct": 0.2, "realized_outcome_pct": -0.4, "baseline_outcome_pct": -0.4},
        {"code": "068270", "session": "20260202", "decision": "SKIP", "p_win": 0.31, "edge_pct": -0.4, "realized_outcome_pct": -4.0, "baseline_outcome_pct": -4.0},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def test_load_validation_frame_supports_edge_and_forward_sources(tmp_path: Path) -> None:
    edge = _edge_ledger(tmp_path / "edge.json")
    frame = load_validation_frame(edge)
    assert frame.iloc[0]["symbol"] == "000250"
    assert "outcome_pct_23bp" in frame.columns

    forward = _forward_jsonl(tmp_path / "ledger.jsonl")
    forward_frame = load_validation_frame(forward)
    assert forward_frame.iloc[0]["symbol"] == "000250"
    assert forward_frame.iloc[0]["baseline_outcome_pct_23bp"] == 2.0

    bad = _edge_ledger(tmp_path / "bad.json", invalid_decision=True)
    with pytest.raises(FrozenPolicyValidationError, match="invalid decision"):
        load_validation_frame(bad)


def test_fresh_validation_pass_unlocks_restricted_rl_precondition(tmp_path: Path) -> None:
    edge = _edge_ledger(tmp_path / "edge.json")
    output = tmp_path / "fresh" / "summary.json"

    payload = run_frozen_policy_validation(
        FrozenPolicyConfig(
            source_path=edge,
            output_path=output,
            run_id="frozen_policy_fresh_realized_fixture",
            fill_mode="realized_full",
            validation_scope="fresh_forward",
            min_trades=1,
            output_root=tmp_path / "fresh",
        )
    )

    assert output.is_file()
    assert payload["artifact_type"] == "frozen_policy_fresh_validation"
    assert payload["policy"]["policy_id"] == "pwin_gt_040_size_050_100_halt_25"
    assert payload["gate"]["verdict"] == "FRESH_VALIDATION_PASS"
    assert payload["gate"]["fresh_validation_pass"] is True
    assert payload["gate"]["implementation_unlocked"] is True
    assert payload["comparison"]["drawdown_improvement"] is True
    assert payload["comparison"]["risk_adjusted_improvement"] is True
    assert "NOT RL" in payload["strategy_label"]
    assert "no broker/orders" in payload["guardrail"]


def test_current_replay_cannot_unlock_even_when_metrics_pass(tmp_path: Path) -> None:
    edge = _edge_ledger(tmp_path / "edge.json")
    output = tmp_path / "fresh" / "summary.json"

    payload = run_frozen_policy_validation(
        FrozenPolicyConfig(
            source_path=edge,
            output_path=output,
            run_id="frozen_policy_replay_fixture",
            fill_mode="realized_full",
            validation_scope="current_replay",
            min_trades=1,
            output_root=tmp_path / "fresh",
        )
    )

    assert payload["comparison"]["fresh_gate_pass"] is True
    assert payload["gate"]["verdict"] == "NOT_FRESH_REPLAY"
    assert payload["gate"]["implementation_unlocked"] is False


def test_frozen_policy_validation_rejects_output_outside_root(tmp_path: Path) -> None:
    edge = _edge_ledger(tmp_path / "edge.json")
    with pytest.raises(FrozenPolicyValidationError, match="output path must be under"):
        run_frozen_policy_validation(
            FrozenPolicyConfig(
                source_path=edge,
                output_path=tmp_path / "outside" / "summary.json",
                run_id="frozen_policy_fixture",
                fill_mode="realized_full",
                validation_scope="fresh_oos",
                min_trades=1,
                output_root=tmp_path / "fresh",
            )
        )
