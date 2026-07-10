import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl.daily_close_slot_gate import validate_close_slot_gate, write_close_slot_gate_artifacts  # noqa: E402
from stom_rl.daily_close_slot_train import CloseSlotTrainConfig, run_close_slot_training  # noqa: E402
from tests.test_stom_rl_daily_close_slot_train import _write_dataset_run  # noqa: E402

def _rewrite_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _train_run(tmp_path: Path, *, with_d3: bool = False):
    dataset = _write_dataset_run(tmp_path / "dataset_root")
    d3_path = None
    if with_d3:
        d3_path = tmp_path / "frozen_d3.csv"
        d3_path.write_text("date,code,score,selected\n2024-04-04,000001,0.9,true\n", encoding="utf-8")
    result = run_close_slot_training(
        CloseSlotTrainConfig(
            dataset_run_id=dataset["run_id"],
            dataset_manifest_sha=dataset["manifest_sha"],
            dataset_artifact_root=dataset["root"],
            output_root=tmp_path / "train_root",
            run_id="train_for_gate",
            total_capital_krw=1_000_000,
            frozen_d3_score_path=d3_path,
        )
    )
    return result


def test_validate_close_slot_gate_passes_with_required_controls_and_watch_status(tmp_path: Path):
    result = _train_run(tmp_path, with_d3=True)

    report = validate_close_slot_gate(result["paths"]["train_manifest"])

    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert report["gate_status"] == "WATCH_RESEARCH_ONLY"
    assert report["round_trip_cost_bp"] == 23
    assert report["cost_sensitivity_bp"] == [0, 23, 46]
    assert report["required_baselines"] == ["deterministic_shuffle_top10_control", "no_trade_control"]
    assert {"deterministic_shuffle_top10_control", "no_trade_control"} <= set(report["present_baselines"])
    assert report["train_only_fit"] is True
    assert report["validation_test_no_retune"] is True
    assert report["fit_summary"]["oos_rows_used_for_fit"] == 0
    assert report["split_policy"]["purge_days"] == 1
    assert report["split_policy"]["embargo_days"] == 1
    assert report["d3_comparator"]["reledgered_through_close_slot_accounting"] is True
    assert "READY" not in report["gate_status"]


def test_validate_close_slot_gate_fail_closed_errors_are_stable(tmp_path: Path):
    result = _train_run(tmp_path)
    manifest_path = Path(result["paths"]["train_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    threshold_path = Path(manifest["artifacts"]["threshold_search"])
    threshold_text = threshold_path.read_text(encoding="utf-8")
    windows_path = Path(manifest["artifacts"]["walk_forward_windows"])
    windows_text = windows_path.read_text(encoding="utf-8")
    replay_path = Path(manifest["artifacts"]["replay_episode_ledgers"])
    replay_text = replay_path.read_text(encoding="utf-8")
    cost_summary_path = Path(manifest["artifacts"]["cost_scenario_summary"])
    cost_summary_text = cost_summary_path.read_text(encoding="utf-8")
    malformed_train_path = tmp_path / "malformed_train_manifest.json"
    malformed_train_path.write_text("{not-json", encoding="utf-8")
    report = validate_close_slot_gate(malformed_train_path)
    assert report["status"] == "BLOCK"
    assert "GATE_MISSING_SCHEMA_VERSION" in report["errors"]
    assert "GATE_MISSING_TRAIN_RUN_ID" in report["errors"]

    non_object_train_path = tmp_path / "non_object_train_manifest.json"
    non_object_train_path.write_text("[]", encoding="utf-8")
    report = validate_close_slot_gate(non_object_train_path)
    assert report["status"] == "BLOCK"
    assert "GATE_MISSING_SCHEMA_VERSION" in report["errors"]

    stale = json.loads(json.dumps(manifest))
    stale["model_build_allowed"] = True
    stale["required_baselines"] = ["momentum_top10_score_and_pick"]
    stale["summary"] = [row for row in stale["summary"] if row["policy"] != "no_trade_control"]
    stale["round_trip_cost_bp"] = 46
    stale["cost_sensitivity_bp"] = [46]
    stale["train_only_fit"] = False
    stale["fit_summary"]["oos_rows_used_for_fit"] = 3
    stale["status"] = "READY"
    stale["readiness_status"] = "READY"
    stale["d3_comparator"] = {"present": True, "reledgered_through_close_slot_accounting": False}

    report = validate_close_slot_gate(stale)

    assert report["status"] == "BLOCK"
    assert {
        "GATE_STALE_OPTIMISTIC_FLAGS",
        "GATE_MISSING_REQUIRED_BASELINE",
        "GATE_MISSING_23BP",
        "GATE_OOS_RETUNING_NOT_BLOCKED",
        "GATE_D3_NOT_RELEDGERED",
        "GATE_READY_STATUS_FOR_UNRESOLVED_D0_D1",
    } <= set(report["errors"])

    malformed = json.loads(json.dumps(manifest))
    malformed["round_trip_cost_bp"] = "bad"
    malformed["cost_sensitivity_bp"] = ["bad"]
    malformed["fit_summary"]["oos_rows_used_for_fit"] = "bad"
    malformed["row_counts"]["policy_score_rows"] = "bad"
    report = validate_close_slot_gate(malformed)
    assert "GATE_MISSING_23BP" in report["errors"]
    assert "GATE_OOS_RETUNING_NOT_BLOCKED" in report["errors"]
    assert "GATE_ROW_COUNT_MISMATCH" in report["errors"]

    scalar_cost_ladder = json.loads(json.dumps(manifest))
    scalar_cost_ladder["cost_sensitivity_bp"] = 23
    report = validate_close_slot_gate(scalar_cost_ladder)
    assert "GATE_MISSING_23BP" in report["errors"]

    nonfinite_numbers = json.loads(json.dumps(manifest))
    nonfinite_numbers["cost_sensitivity_bp"] = [float("inf")]
    nonfinite_numbers["row_counts"]["walk_forward_windows"] = float("inf")
    report = validate_close_slot_gate(nonfinite_numbers)
    assert "GATE_MISSING_23BP" in report["errors"]
    assert "GATE_ROW_COUNT_MISMATCH" in report["errors"]

    downgraded_schema = json.loads(json.dumps(manifest))
    downgraded_schema["schema_version"] = 1
    report = validate_close_slot_gate(downgraded_schema)
    assert "GATE_MISSING_SCHEMA_VERSION" in report["errors"]
    missing_model_schema = json.loads(json.dumps(manifest))
    del missing_model_schema["cost_model_schema_version"]
    report = validate_close_slot_gate(missing_model_schema)
    assert "GATE_V2_COST_MODEL_SCHEMA_MISSING" in report["errors"]

    missing_cost_scenario = json.loads(json.dumps(manifest))
    del missing_cost_scenario["cost_scenarios"]["zero_control_0bp"]
    report = validate_close_slot_gate(missing_cost_scenario)
    assert "GATE_V2_COST_SCENARIO_MISSING_BASE_OR_STRESS" in report["errors"]

    missing_cost_component = json.loads(json.dumps(manifest))
    del missing_cost_component["cost_scenarios"]["base_23bp"]["sell_tax_bp"]
    report = validate_close_slot_gate(missing_cost_component)
    assert "GATE_V2_COST_COMPONENT_MISSING" in report["errors"]

    scalar_cost_accounting = json.loads(json.dumps(manifest))
    scalar_cost_accounting["cost_scenarios"]["base_23bp"]["components_bp"] = {"total": 23.0}
    report = validate_close_slot_gate(scalar_cost_accounting)
    assert "GATE_V2_SCALAR_ONLY_COST_ACCOUNTING" in report["errors"]
    bad_cost_components = json.loads(json.dumps(manifest))
    bad_cost_components["cost_scenarios"]["base_23bp"]["sell_tax_bp"] = 0.0
    report = validate_close_slot_gate(bad_cost_components)
    assert "GATE_V2_COST_ROUND_TRIP_DERIVATION_MISMATCH" in report["errors"]

    missing_threshold = json.loads(json.dumps(manifest))
    del missing_threshold["artifacts"]["threshold_search"]
    report = validate_close_slot_gate(missing_threshold)
    assert "GATE_V2_THRESHOLD_GRID_MISSING" in report["errors"]

    promoted_shuffle = json.loads(json.dumps(manifest))
    for row in promoted_shuffle["summary"]:
        if row["policy"] == "deterministic_shuffle_top10_control":
            row["policy_action_allowed"] = True
    report = validate_close_slot_gate(promoted_shuffle)
    assert "GATE_V2_SHUFFLE_POLICY_PROMOTION" in report["errors"]

    threshold_path.unlink()
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_THRESHOLD_GRID_MISSING" in report["errors"]
    threshold_path.write_text(threshold_text, encoding="utf-8")

    threshold_rows = _read_csv(threshold_path)
    threshold_rows[0]["split"] = "val"
    threshold_rows[0]["oos_rows_used_for_fit"] = "1"
    _rewrite_csv(threshold_path, threshold_rows)
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_THRESHOLD_OOS_LEAKAGE" in report["errors"]
    threshold_path.write_text(threshold_text, encoding="utf-8")

    windows_payload = json.loads(windows_text)
    windows_payload["oos_rows_used_for_fit"] = 1
    windows_payload["windows"][0]["oos_rows_used_for_fit"] = 1
    windows_path.write_text(json.dumps(windows_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_OOS_ROWS_USED_FOR_FIT_NONZERO" in report["errors"]
    windows_payload = json.loads(windows_text)
    windows_payload["oos_rows_used_for_fit"] = float("inf")
    windows_payload["windows"][0]["oos_rows_used_for_fit"] = float("inf")
    windows_path.write_text(json.dumps(windows_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_OOS_ROWS_USED_FOR_FIT_NONZERO" in report["errors"]
    windows_path.write_text(windows_text, encoding="utf-8")

    windows_payload = json.loads(windows_text)
    windows_payload["windows"] = [
        row for row in windows_payload["windows"] if row.get("feedback_source_split") != "none_frozen_held_out"
    ]
    windows_path.write_text(json.dumps(windows_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_HELD_OUT_FREEZE_MISSING" in report["errors"]
    windows_path.write_text(windows_text, encoding="utf-8")

    windows_payload = json.loads(windows_text)
    for row in windows_payload["windows"]:
        if row.get("feedback_source_split") == "none_frozen_held_out":
            row["held_out_replay_splits"] = ["val"]
            row["frozen_replay_start_date"] = ""
            break
    windows_path.write_text(json.dumps(windows_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_HELD_OUT_FREEZE_MISSING" in report["errors"]
    windows_path.write_text(windows_text, encoding="utf-8")

    windows_path.write_text("{not-json", encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_WF_WINDOWS_MISSING" in report["errors"]
    windows_path.write_text(windows_text, encoding="utf-8")

    replay_path.unlink()
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_REPLAY_LEDGER_MISSING" in report["errors"]
    replay_path.write_text(replay_text, encoding="utf-8")

    replay_payload = json.loads(replay_text)
    replay_payload["episodes"][0]["oos_rows_used_for_fit"] = 1
    replay_path.write_text(json.dumps(replay_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_OOS_ROWS_USED_FOR_FIT_NONZERO" in report["errors"]
    replay_path.write_text(replay_text, encoding="utf-8")
    replay_payload = json.loads(replay_text)
    replay_payload["episodes"][0]["oos_rows_used_for_fit"] = float("inf")
    replay_path.write_text(json.dumps(replay_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_OOS_ROWS_USED_FOR_FIT_NONZERO" in report["errors"]
    replay_path.write_text(replay_text, encoding="utf-8")


    replay_payload = json.loads(replay_text)
    replay_payload["episodes"][0]["slot_feedback"] = [None]
    replay_path.write_text(json.dumps(replay_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_REPLAY_LEDGER_MISSING" in report["errors"]
    replay_path.write_text(replay_text, encoding="utf-8")

    replay_payload = json.loads(replay_text)
    replay_payload["episodes"] = [
        episode for episode in replay_payload["episodes"] if episode.get("replay_split") != "test"
    ]
    replay_path.write_text(json.dumps(replay_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_REPLAY_LEDGER_MISSING" in report["errors"]
    assert "GATE_ROW_COUNT_MISMATCH" in report["errors"]
    replay_path.write_text(replay_text, encoding="utf-8")

    replay_payload = json.loads(replay_text)
    replay_payload["episodes"][0]["slot_feedback"] = 1
    replay_path.write_text(json.dumps(replay_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_REPLAY_LEDGER_MISSING" in report["errors"]
    replay_path.write_text(replay_text, encoding="utf-8")

    cost_rows = _read_csv(cost_summary_path)
    cost_rows[0]["sell_tax_bp"] = "99"
    cost_rows[0]["total_component_bp"] = "99"
    _rewrite_csv(cost_summary_path, cost_rows)
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_COST_ROUND_TRIP_DERIVATION_MISMATCH" in report["errors"]
    cost_summary_path.write_text(cost_summary_text, encoding="utf-8")
    cost_rows = _read_csv(cost_summary_path)
    cost_rows[0]["selected_count"] = "not-an-int"
    cost_rows[0]["hold_cash_count"] = "not-an-int"
    _rewrite_csv(cost_summary_path, cost_rows)
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_SELECTED_HOLD_COUNT_INVALID" in report["errors"]
    cost_summary_path.write_text(cost_summary_text, encoding="utf-8")

    replay_path = Path(manifest["artifacts"]["replay_episode_ledgers"])
    replay_payload = json.loads(replay_path.read_text(encoding="utf-8"))
    for episode in replay_payload["episodes"]:
        if episode["replay_split"] == "test":
            episode["slot_feedback"][0]["feedback_used_for_fit"] = True
            break
    replay_path.write_text(json.dumps(replay_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_V2_FEEDBACK_SOURCE_NOT_TRAIN" in report["errors"]
    replay_path.write_text(replay_text, encoding="utf-8")

    hidden_blockers = json.loads(json.dumps(manifest))
    hidden_blockers["upstream_gate_blockers"] = []
    hidden_blockers["status"] = "READY"
    hidden_blockers["readiness_status"] = "READY"
    report = validate_close_slot_gate(hidden_blockers)
    assert "GATE_READY_STATUS_FOR_UNRESOLVED_D0_D1" in report["errors"]

    dataset_manifest_path = Path(manifest["dataset_manifest_path"])
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    dataset_manifest["cost_sensitivity_bp"] = ["bad"]
    dataset_manifest_path.write_text(json.dumps(dataset_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_DATASET_LINEAGE_NOT_PASS" in report["errors"]
    dataset_manifest["cost_sensitivity_bp"] = [0, 23, 46]
    dataset_manifest_path.write_text(json.dumps(dataset_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    dataset_manifest_path.write_text("{not-json", encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_DATASET_LINEAGE_NOT_PASS" in report["errors"]
    dataset_manifest_path.write_text(json.dumps(dataset_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    dataset_manifest_path.write_text("[]", encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_DATASET_LINEAGE_NOT_PASS" in report["errors"]
    dataset_manifest_path.write_text(json.dumps(dataset_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    dataset_manifest_path = Path(manifest["dataset_manifest_path"])
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    dataset_manifest["split_policy"]["purge_days"] = 0
    dataset_manifest["split_policy"]["embargo_days"] = 0
    dataset_manifest_path.write_text(json.dumps(dataset_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_MISSING_SPLIT_EVIDENCE" in report["errors"]

    baseline_path = Path(manifest["artifacts"]["baseline_summary"])
    baseline_lines = baseline_path.read_text(encoding="utf-8").splitlines()
    baseline_path.write_text("\n".join([line for line in baseline_lines if "no_trade_control" not in line]) + "\n", encoding="utf-8")
    report = validate_close_slot_gate(manifest)
    assert "GATE_MISSING_REQUIRED_BASELINE" in report["errors"]

    no_audit = json.loads(json.dumps(manifest))
    policy_scores = Path(no_audit["artifacts"]["policy_scores"])
    text = policy_scores.read_text(encoding="utf-8")
    policy_scores.write_text(text.replace("dataset_run_id,", ""), encoding="utf-8")
    report = validate_close_slot_gate(no_audit)
    assert "GATE_HASH_MISMATCH" in report["errors"]
    assert "GATE_MISSING_POLICY_SCORE_AUDIT" in report["errors"]

    d3_result = _train_run(tmp_path / "malformed_d3", with_d3=True)
    d3_manifest = json.loads(Path(d3_result["paths"]["train_manifest"]).read_text(encoding="utf-8"))
    d3_date_ledgers = Path(d3_manifest["artifacts"]["date_ledgers"])
    d3_date_ledgers.write_text("{not-json", encoding="utf-8")
    report = validate_close_slot_gate(d3_manifest)
    assert "GATE_D3_NOT_RELEDGERED" in report["errors"]


def test_write_close_slot_gate_artifacts_checks_train_hash_and_duplicate_run(tmp_path: Path):
    result = _train_run(tmp_path)
    train_manifest = result["manifest"]

    written = write_close_slot_gate_artifacts(
        train_manifest_path=result["paths"]["train_manifest"],
        train_manifest_sha=train_manifest["manifest_sha"],
        output_root=tmp_path / "gate_root",
        run_id="gate_unit",
    )

    assert written["gate_validation_status"] == "PASS"
    assert Path(written["gate_report_path"]).exists()
    gate_manifest = json.loads(Path(written["gate_manifest_path"]).read_text(encoding="utf-8"))
    assert gate_manifest["status"] == "WATCH_RESEARCH_ONLY"
    assert gate_manifest["promotion_allowed"] is False
    assert gate_manifest["source_run_ids"]["train_run_id"] == "train_for_gate"

    malformed_train_path = tmp_path / "writer_malformed_train_manifest.json"
    malformed_train_path.write_text("{not-json", encoding="utf-8")
    malformed_written = write_close_slot_gate_artifacts(
        train_manifest_path=malformed_train_path,
        train_manifest_sha="unavailable",
        output_root=tmp_path / "gate_root",
        run_id="malformed_manifest",
    )
    assert malformed_written["gate_validation_status"] == "BLOCK"
    malformed_report = json.loads(Path(malformed_written["gate_report_path"]).read_text(encoding="utf-8"))
    assert "GATE_MISSING_SCHEMA_VERSION" in malformed_report["errors"]
    with pytest.raises(ValueError, match="sha mismatch"):
        write_close_slot_gate_artifacts(
            train_manifest_path=result["paths"]["train_manifest"],
            train_manifest_sha="wrong",
            output_root=tmp_path / "gate_root",
            run_id="bad_hash",
        )
    with pytest.raises(FileExistsError):
        write_close_slot_gate_artifacts(
            train_manifest_path=result["paths"]["train_manifest"],
            train_manifest_sha=train_manifest["manifest_sha"],
            output_root=tmp_path / "gate_root",
            run_id="gate_unit",
        )
