import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from finetune.f14_decision_gate import (  # noqa: E402
    DecisionGateError,
    SUPERVISED_FORECAST_LABEL,
    decide_f14_gate,
)


def _evidence(decision="TUNING_HARMFUL"):
    return {
        "schema": "task13_r5_attribution_evidence.v1",
        "created_for": "G013",
        "research_only": True,
        "no_live_broker_profit_go_rl_or_trading_alpha_claim": True,
        "cost_gate_bp": 23,
        "hashes": {"hash_manifest": ".omo/evidence/task-13-r5-attribution/hashes.json"},
        "missing_nan_hash_checks": {
            "hashes_json_present": True,
            "source_input_output_hashes_present": True,
            "selected_windows_is_681": True,
            "metric_nan_detected": False,
            "comparison_jsons_present": True,
            "tokenizer_mse_nan": False,
        },
        "decision": decision,
    }


def _report(decision="TUNING_HARMFUL"):
    return f"# Attribution result\n\n## Decision: {decision}\n\n## F14 status\nNot launched.\n"


def _valid_prereg():
    return {
        "dated_path": "docs/stom_kronos_f14_prereg_2026-07-12.md",
        "sha256": "a" * 64,
        "model_label": SUPERVISED_FORECAST_LABEL,
        "horizon_seconds": 300,
        "costs_bp": [0, 23, 46],
        "primary_cost_bp": 23,
        "stages": ["smoke", "full"],
        "seeds": [11, 23, 42],
        "stop_criteria": {
            "smoke": ["stop on NaN or schema/hash mismatch", "stop if smoke metrics are non-finite"],
            "full": ["stop on any split/control mismatch", "stop unless smoke passed first"],
        },
        "runnable_command": "python finetune/run_f14.py --horizon-seconds 300 --prereg docs/stom_kronos_f14_prereg_2026-07-12.md",
    }


@pytest.mark.parametrize(
    ("decision", "action_fragment"),
    [
        ("NO_SIGNAL", "data/horizon research"),
        ("TUNING_HARMFUL", "data/tokenizer repair"),
        ("INCONCLUSIVE", "defect-specific preregistered R5 rerun"),
        ("TUNING_HELPED_COST", "new dated F14 preregistration gate"),
    ],
)
def test_all_four_branches_fail_closed_without_complete_prereg(decision, action_fragment):
    gate = decide_f14_gate(_evidence(decision), report_text=_report(decision))

    assert gate["decision"] == decision
    assert gate["reason"] == decision
    assert gate["model_label"] == SUPERVISED_FORECAST_LABEL
    assert gate["f14_execution_allowed"] is False
    assert gate["runnable_command"] is None
    assert action_fragment in gate["action"]
    assert gate["f14_prereg_allowed"] is (decision == "TUNING_HELPED_COST")


def test_current_g013_tuning_harmful_blocks_f14_and_prereg():
    gate = decide_f14_gate(_evidence("TUNING_HARMFUL"), report_text=_report("TUNING_HARMFUL"))

    assert gate["f14_execution_allowed"] is False
    assert gate["f14_prereg_allowed"] is False
    assert gate["reason"] == "TUNING_HARMFUL"
    assert gate["model_label"] == SUPERVISED_FORECAST_LABEL
    assert gate["runnable_command"] is None
    assert gate["blocked"] is True


def test_valid_synthetic_tuning_helped_cost_prereg_opens_execution_permission():
    gate = decide_f14_gate(
        _evidence("TUNING_HELPED_COST"),
        report_text=_report("TUNING_HELPED_COST"),
        prereg=_valid_prereg(),
    )

    assert gate["f14_execution_allowed"] is True
    assert gate["f14_prereg_allowed"] is True
    assert gate["blocked"] is False
    assert gate["prereg"]["horizon_seconds"] == 300
    assert gate["prereg"]["costs_bp"] == [0, 23, 46]
    assert gate["prereg"]["primary_cost_bp"] == 23
    assert gate["prereg"]["stages"] == ["smoke", "full"]
    assert gate["runnable_command"] == "python finetune/run_f14.py --horizon-seconds 300 --prereg docs/stom_kronos_f14_prereg_2026-07-12.md"


@pytest.mark.parametrize("decision", ["NO_SIGNAL", "TUNING_HARMFUL", "INCONCLUSIVE"])
def test_disallowed_decisions_reject_f14_prereg_submission(decision):
    with pytest.raises(DecisionGateError, match="cannot submit an F14 preregistration"):
        decide_f14_gate(_evidence(decision), report_text=_report(decision), prereg=_valid_prereg())


def test_inconclusive_allows_only_one_defect_specific_rerun():
    first = decide_f14_gate(_evidence("INCONCLUSIVE"), report_text=_report("INCONCLUSIVE"), inconclusive_reruns_used=0)
    second = decide_f14_gate(_evidence("INCONCLUSIVE"), report_text=_report("INCONCLUSIVE"), inconclusive_reruns_used=1)

    assert first["inconclusive_rerun_allowed"] is True
    assert second["inconclusive_rerun_allowed"] is False
    with pytest.raises(DecisionGateError, match="at most one"):
        decide_f14_gate(_evidence("INCONCLUSIVE"), report_text=_report("INCONCLUSIVE"), inconclusive_reruns_used=2)


def test_report_decision_mismatch_is_rejected():
    with pytest.raises(DecisionGateError, match="report/JSON decision mismatch"):
        decide_f14_gate(_evidence("TUNING_HARMFUL"), report_text=_report("NO_SIGNAL"))


def test_missing_report_is_rejected_before_any_unlock():
    with pytest.raises(DecisionGateError, match="report text is required"):
        decide_f14_gate(_evidence("TUNING_HELPED_COST"), prereg=_valid_prereg())


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    [
        ("selected_windows_is_681", False),
        ("metric_nan_detected", True),
        ("comparison_jsons_present", False),
        ("tokenizer_mse_nan", True),
    ],
)
def test_unsafe_integrity_flags_block_tuning_helped_cost(field, unsafe_value):
    evidence = _evidence("TUNING_HELPED_COST")
    evidence["missing_nan_hash_checks"][field] = unsafe_value
    with pytest.raises(DecisionGateError):
        decide_f14_gate(evidence, report_text=_report("TUNING_HELPED_COST"), prereg=_valid_prereg())


def test_unknown_missing_decision_and_missing_hash_fail_closed():
    with pytest.raises(DecisionGateError, match="unknown or missing"):
        decide_f14_gate(_evidence("NOT_A_DECISION"), report_text=_report("NO_SIGNAL"))

    missing = _evidence("TUNING_HARMFUL")
    del missing["hashes"]
    with pytest.raises(DecisionGateError, match="missing evidence hash section"):
        decide_f14_gate(missing, report_text=_report("TUNING_HARMFUL"))


def test_malformed_prereg_cost_stage_label_fields_are_rejected():
    bad_label = _valid_prereg()
    bad_label["model_label"] = "trading alpha"
    with pytest.raises(DecisionGateError, match="supervised forecast label"):
        decide_f14_gate(_evidence("TUNING_HELPED_COST"), report_text=_report("TUNING_HELPED_COST"), prereg=bad_label)

    bad_costs = _valid_prereg()
    bad_costs["costs_bp"] = [0, 23]
    with pytest.raises(DecisionGateError, match="costs must be exactly"):
        decide_f14_gate(_evidence("TUNING_HELPED_COST"), report_text=_report("TUNING_HELPED_COST"), prereg=bad_costs)

    bad_stages = _valid_prereg()
    bad_stages["stages"] = ["full", "smoke"]
    with pytest.raises(DecisionGateError, match="smoke then full"):
        decide_f14_gate(_evidence("TUNING_HELPED_COST"), report_text=_report("TUNING_HELPED_COST"), prereg=bad_stages)


@pytest.mark.parametrize(
    ("command_value", "message"),
    [
        (None, "nonempty runnable_command"),
        ("", "nonempty runnable_command"),
        ("python finetune/run_f14.py --horizon-seconds 300", "must be exactly"),
        ("python finetune/run_f14.py --horizon-seconds 60 --prereg docs/stom_kronos_f14_prereg_2026-07-12.md", "horizon to 300"),
        ("python finetune/run_f14.py --horizon-seconds 300 --prereg docs/other_f14_prereg_2026-07-12.md", "dated prereg path"),
        ("python finetune/run_other.py --horizon-seconds 300 --prereg docs/stom_kronos_f14_prereg_2026-07-12.md", "finetune/run_f14.py"),
        ("python finetune/run_f14.py --horizon-seconds 300 --prereg docs/stom_kronos_f14_prereg_2026-07-12.md; python evil.py", "shell metacharacters"),
    ],
)
def test_malformed_missing_empty_or_injected_runnable_command_is_rejected(command_value, message):
    prereg = _valid_prereg()
    if command_value is None:
        del prereg["runnable_command"]
    else:
        prereg["runnable_command"] = command_value

    with pytest.raises(DecisionGateError, match=message):
        decide_f14_gate(_evidence("TUNING_HELPED_COST"), report_text=_report("TUNING_HELPED_COST"), prereg=prereg)


def test_cli_fails_closed_json_on_bad_input(tmp_path, capsys):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_evidence("UNKNOWN")), encoding="utf-8")

    from finetune.f14_decision_gate import main

    assert main(["--evidence", str(evidence_path)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["f14_execution_allowed"] is False
    assert out["f14_prereg_allowed"] is False
    assert out["runnable_command"] is None
