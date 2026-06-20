"""Tests for the P2 risk-policy model-build readiness lab."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stom_rl.factory.risk_policy_lab import (
    RiskPolicyLabError,
    load_edge_ledger,
    run_risk_policy_lab,
)


def _edge_ledger(path: Path, *, invalid_decision: bool = False) -> Path:
    rows = [
        {"symbol": "000250", "session": "20260102", "decision": "TAKE", "p_win": 0.62, "edge_pct": 0.8, "net_pct_23bp": 2.0},
        {"symbol": "035720", "session": "20260102", "decision": "TAKE", "p_win": 0.42, "edge_pct": 0.2, "net_pct_23bp": -0.6},
        {"symbol": "068270", "session": "20260103", "decision": "SKIP", "p_win": 0.31, "edge_pct": -0.4, "net_pct_23bp": -2.0},
        {"symbol": "000660", "session": "20260103", "decision": "TAKE", "p_win": 0.58, "edge_pct": 0.7, "net_pct_23bp": 1.5},
        {"symbol": "005930", "session": "20260104", "decision": "TAKE", "p_win": 0.41, "edge_pct": 0.1, "net_pct_23bp": -0.4},
    ]
    if invalid_decision:
        rows[0]["decision"] = "HOLD"
    path.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    return path


def test_load_edge_ledger_preserves_codes_and_rejects_invalid_decisions(tmp_path: Path) -> None:
    path = _edge_ledger(tmp_path / "edge.json")
    frame = load_edge_ledger(path)
    assert frame.iloc[0]["symbol"] == "000250"
    assert set(frame["decision"]) == {"TAKE", "SKIP"}

    bad = _edge_ledger(tmp_path / "bad.json", invalid_decision=True)
    with pytest.raises(RiskPolicyLabError, match="invalid decisions"):
        load_edge_ledger(bad)


def test_run_risk_policy_lab_writes_candidate_gate_and_guardrails(tmp_path: Path) -> None:
    edge = _edge_ledger(tmp_path / "edge.json")
    output = tmp_path / "risk" / "summary.json"

    payload = run_risk_policy_lab(
        edge,
        output,
        run_id="risk_policy_fixture",
        fill_mode="realized_full",
        output_root=tmp_path / "risk",
        min_total_delta_pct=-10.0,
    )

    assert output.is_file()
    assert payload["artifact_type"] == "risk_policy_lab"
    assert payload["cost_bps"] == 23.0
    assert "NOT RL" in payload["strategy_label"]
    assert "no broker/orders" in payload["guardrail"]
    assert payload["best"]["policy"]["policy_id"]
    assert payload["best"]["comparison"]["risk_adjusted_improvement"] is True
    assert payload["gate"]["implementation_unlocked"] is False
    assert "requires preregistered fresh OOS" in payload["gate"]["unlock_note"]


def test_run_risk_policy_lab_rejects_output_outside_root(tmp_path: Path) -> None:
    edge = _edge_ledger(tmp_path / "edge.json")
    with pytest.raises(RiskPolicyLabError, match="output path must be under"):
        run_risk_policy_lab(
            edge,
            tmp_path / "outside" / "summary.json",
            run_id="risk_policy_fixture",
            fill_mode="realized_full",
            output_root=tmp_path / "risk",
        )
