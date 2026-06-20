import math
import statistics

import pytest

from stom_rl.opening_30m_rl_candidate_gate import (
    CandidateGateInput,
    build_policy_diagnostics,
    build_sample_power,
    evaluate_candidate_gate,
)


def test_candidate_promotion_requires_oos_controls_ablation_and_baseline():
    passed = evaluate_candidate_gate(
        CandidateGateInput(
            candidate_id="dqn",
            split_hash="split123",
            validation_net_return_pct=1.0,
            oos_net_return_pct=3.0,
            no_trade_net_return_pct=0.0,
            buy_and_hold_net_return_pct=1.0,
            ts_imb_rule_net_return_pct=2.0,
            cost_bps=23.0,
            controls_passed=True,
            ablations_passed=True,
            trade_count=4,
            max_drawdown_pct=-1.0,
        )
    )
    failed = evaluate_candidate_gate(
        CandidateGateInput(
            candidate_id="dqn",
            split_hash="split123",
            validation_net_return_pct=1.0,
            oos_net_return_pct=1.0,
            no_trade_net_return_pct=0.0,
            buy_and_hold_net_return_pct=1.0,
            ts_imb_rule_net_return_pct=2.0,
            cost_bps=23.0,
            controls_passed=True,
            ablations_passed=True,
            trade_count=4,
            max_drawdown_pct=-1.0,
        )
    )

    assert passed["verdict"] == "GO_CANDIDATE"
    assert failed["verdict"] == "NO-GO_BASELINE"
    assert "failed_baseline:ts_imb_rule" in failed["blocking_reasons"]


def test_candidate_gate_writes_equity_curve_and_time_bucket_metrics():
    artifact = evaluate_candidate_gate(
        CandidateGateInput(
            candidate_id="ppo",
            split_hash="split123",
            validation_net_return_pct=2.0,
            oos_net_return_pct=3.0,
            no_trade_net_return_pct=0.0,
            buy_and_hold_net_return_pct=1.0,
            ts_imb_rule_net_return_pct=2.0,
            cost_bps=23.0,
            controls_passed=True,
            ablations_passed=True,
            trade_count=3,
            max_drawdown_pct=-0.5,
        )
    )

    assert artifact["equity_curve"][-1]["net_return_pct"] == 3.0
    assert artifact["time_bucket_performance"][0]["trade_count"] == 3
    assert artifact["metrics"]["oos_validation_gap_pct"] == 1.0


def test_candidate_promotion_blocks_unacceptable_drawdown():
    artifact = evaluate_candidate_gate(
        CandidateGateInput(
            candidate_id="dqn",
            split_hash="split123",
            validation_net_return_pct=1.0,
            oos_net_return_pct=3.0,
            no_trade_net_return_pct=0.0,
            buy_and_hold_net_return_pct=1.0,
            ts_imb_rule_net_return_pct=2.0,
            cost_bps=23.0,
            controls_passed=True,
            ablations_passed=True,
            trade_count=4,
            max_drawdown_pct=-20.0,
            max_drawdown_limit_pct=-10.0,
        )
    )

    assert artifact["verdict"] == "NO-GO_BASELINE"
    assert "failed_mdd" in artifact["blocking_reasons"]


def test_policy_diagnostics_flags_single_action_dominance():
    diagnostics = build_policy_diagnostics(
        oos_action_distribution={"counts": {"0": 96, "1": 4}, "entropy": 0.1674, "dominant_action_fraction": 0.96, "total_steps": 100},
        ablation_rows=[{"oos_net_return_pct": 1.0}, {"oos_net_return_pct": 2.0}],
    )

    assert diagnostics["single_action_dominant"] is True
    assert diagnostics["ablations_all_identical"] is False
    assert diagnostics["degenerate"] is True
    assert diagnostics["diagnostic_label"] == "DEGENERATE_POLICY"
    assert "training failure, not market evidence" in diagnostics["guardrail"]


def test_policy_diagnostics_flags_identical_ablations_including_full():
    diagnostics = build_policy_diagnostics(
        oos_action_distribution={"counts": {"0": 5, "1": 5}, "entropy": 0.6931, "dominant_action_fraction": 0.5, "total_steps": 10},
        ablation_rows=[
            {"feature_set_id": "full_context", "oos_net_return_pct": 1.25},
            {"feature_set_id": "no_participant_pressure", "oos_net_return_pct": 1.25},
            {"feature_set_id": "minimal_price_volume", "oos_net_return_pct": 1.25},
        ],
    )

    assert diagnostics["single_action_dominant"] is False
    assert diagnostics["ablations_all_identical"] is True
    assert diagnostics["degenerate"] is True
    assert diagnostics["diagnostic_label"] == "DEGENERATE_POLICY"


def test_policy_diagnostics_non_degenerate_case():
    diagnostics = build_policy_diagnostics(
        oos_action_distribution={"counts": {"0": 6, "1": 4}, "entropy": 0.673, "dominant_action_fraction": 0.6, "total_steps": 10},
        ablation_rows=[{"oos_net_return_pct": 1.0}, {"oos_net_return_pct": 2.0}],
    )

    assert diagnostics["single_action_dominant"] is False
    assert diagnostics["ablations_all_identical"] is False
    assert diagnostics["degenerate"] is False
    assert diagnostics["diagnostic_label"] == ""


def test_sample_power_insufficient_trades():
    power = build_sample_power(oos_trade_count=6, min_required=100)

    assert power["oos_trades"] == 6
    assert power["min_required"] == 100
    assert power["sufficient"] is False
    assert power["ci_width_pct"] is None


def test_sample_power_sufficient_with_ci_width():
    returns = [0.5, -0.2, 0.3, 0.1]
    power = build_sample_power(oos_trade_count=120, min_required=100, oos_returns_pct=returns)

    assert power["sufficient"] is True
    assert power["ci_width_pct"] == pytest.approx(1.96 * 2.0 * statistics.stdev(returns) / math.sqrt(len(returns)))


def test_sample_power_ci_width_none_below_two_samples():
    power = build_sample_power(oos_trade_count=1, min_required=100, oos_returns_pct=[0.5])

    assert power["sufficient"] is False
    assert power["ci_width_pct"] is None


def test_candidate_gate_existing_inputs_keep_verdict_and_gain_new_keys():
    artifact = evaluate_candidate_gate(
        CandidateGateInput(
            candidate_id="dqn",
            split_hash="split123",
            validation_net_return_pct=1.0,
            oos_net_return_pct=3.0,
            no_trade_net_return_pct=0.0,
            buy_and_hold_net_return_pct=1.0,
            ts_imb_rule_net_return_pct=2.0,
            cost_bps=23.0,
            controls_passed=True,
            ablations_passed=True,
            trade_count=4,
            max_drawdown_pct=-1.0,
        )
    )

    assert artifact["verdict"] == "GO_CANDIDATE"
    assert artifact["diagnostic_label"] == ""
    assert artifact["policy_diagnostics"]["degenerate"] is False
    assert artifact["sample_power"]["oos_trades"] == 4
    assert artifact["sample_power"]["sufficient"] is True


def test_candidate_gate_labels_degenerate_no_go_without_changing_verdict():
    artifact = evaluate_candidate_gate(
        CandidateGateInput(
            candidate_id="dqn",
            split_hash="split123",
            validation_net_return_pct=1.0,
            oos_net_return_pct=1.0,
            no_trade_net_return_pct=0.0,
            buy_and_hold_net_return_pct=1.0,
            ts_imb_rule_net_return_pct=2.0,
            cost_bps=23.0,
            controls_passed=True,
            ablations_passed=True,
            trade_count=4,
            max_drawdown_pct=-1.0,
            oos_action_distribution={"counts": {"0": 97, "1": 3}, "entropy": 0.1347, "dominant_action_fraction": 0.97, "total_steps": 100},
        )
    )

    assert artifact["verdict"] == "NO-GO_BASELINE"
    assert "failed_baseline:ts_imb_rule" in artifact["blocking_reasons"]
    assert artifact["diagnostic_label"] == "DEGENERATE_POLICY"
    assert artifact["policy_diagnostics"]["degenerate"] is True


def test_candidate_gate_degenerate_go_candidate_keeps_empty_label():
    artifact = evaluate_candidate_gate(
        CandidateGateInput(
            candidate_id="ppo",
            split_hash="split123",
            validation_net_return_pct=1.0,
            oos_net_return_pct=3.0,
            no_trade_net_return_pct=0.0,
            buy_and_hold_net_return_pct=1.0,
            ts_imb_rule_net_return_pct=2.0,
            cost_bps=23.0,
            controls_passed=True,
            ablations_passed=True,
            trade_count=4,
            max_drawdown_pct=-1.0,
            oos_action_distribution={"counts": {"0": 99, "1": 1}, "entropy": 0.056, "dominant_action_fraction": 0.99, "total_steps": 100},
        )
    )

    assert artifact["verdict"] == "GO_CANDIDATE"
    assert artifact["diagnostic_label"] == ""
    assert artifact["policy_diagnostics"]["single_action_dominant"] is True
