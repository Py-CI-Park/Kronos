import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl.daily_close_slot_train import (  # noqa: E402
    CloseSlotTrainConfig,
    load_close_slot_dataset_run,
    run_close_slot_training,
)


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict], fallback: list[str]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else fallback
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_dataset_run(root: Path, run_id: str = "dataset_unit") -> dict:
    out = root / run_id
    out.mkdir(parents=True)
    panel_rows = [
        {
            "date": "2024-04-01",
            "exit_date": "2024-04-02",
            "table": "A000001",
            "code": "000001",
            "split": "train",
            "entry_close": 1000,
            "next_close": 1100,
            "future_return_1d": 0.10,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": 0.5,
            "feature_a": 1.0,
        },
        {
            "date": "2024-04-01",
            "exit_date": "2024-04-02",
            "table": "A000002",
            "code": "000002",
            "split": "train",
            "entry_close": 1000,
            "next_close": 900,
            "future_return_1d": -0.10,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": -0.5,
            "feature_a": -1.0,
        },
        {
            "date": "2024-04-02",
            "exit_date": "2024-04-03",
            "table": "A000001",
            "code": "000001",
            "split": "train",
            "entry_close": 1000,
            "next_close": 1020,
            "future_return_1d": 0.02,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": 0.9,
            "feature_a": 2.0,
        },
        {
            "date": "2024-04-02",
            "exit_date": "2024-04-03",
            "table": "A000002",
            "code": "000002",
            "split": "train",
            "entry_close": 1000,
            "next_close": 980,
            "future_return_1d": -0.02,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": -0.9,
            "feature_a": -2.0,
        },
        {
            "date": "2024-04-03",
            "exit_date": "2024-04-04",
            "table": "A000001",
            "code": "000001",
            "split": "val",
            "entry_close": 1000,
            "next_close": 1030,
            "future_return_1d": 0.03,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": 0.1,
            "feature_a": 0.25,
        },
        {
            "date": "2024-04-03",
            "exit_date": "2024-04-04",
            "table": "A000002",
            "code": "000002",
            "split": "val",
            "entry_close": 1000,
            "next_close": 970,
            "future_return_1d": -0.03,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": -0.1,
            "feature_a": -0.25,
        },
        {
            "date": "2024-04-04",
            "exit_date": "2024-04-05",
            "table": "A000001",
            "code": "000001",
            "split": "test",
            "entry_close": 1000,
            "next_close": 1040,
            "future_return_1d": 0.04,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": 0.05,
            "feature_a": 0.15,
        },
        {
            "date": "2024-04-04",
            "exit_date": "2024-04-05",
            "table": "A000002",
            "code": "000002",
            "split": "test",
            "entry_close": 1000,
            "next_close": 960,
            "future_return_1d": -0.04,
            "eligible_for_selection": True,
            "candidate_score_causal_momentum": -0.05,
            "feature_a": -0.15,
        },
    ]
    paths = {
        "close_slot_panel": out / "close_slot_panel.csv",
        "candidate_scores_input_schema": out / "candidate_scores_input_schema.json",
        "candidate_score_rows": out / "candidate_score_rows.csv",
        "feature_contract": out / "feature_contract.json",
        "label_audit": out / "label_audit.csv",
        "split_summary": out / "split_summary.json",
        "source_hashes": out / "source_hashes.json",
    }
    _write_csv(paths["close_slot_panel"], panel_rows, [])
    _write_csv(paths["candidate_score_rows"], panel_rows, [])
    _write_csv(paths["label_audit"], panel_rows, [])
    paths["candidate_scores_input_schema"].write_text(json.dumps({"selected_code_lists": "test_or_replay_adapter_only_not_policy_action"}), encoding="utf-8")
    paths["feature_contract"].write_text(json.dumps({"feature_columns": ["feature_a", "candidate_score_causal_momentum"]}), encoding="utf-8")
    paths["split_summary"].write_text(json.dumps({"train": 2, "val": 2, "test": 2}), encoding="utf-8")
    paths["source_hashes"].write_text(json.dumps({"daily_db_fingerprint": "unit-db", "universe_manifest_sha": "unit-universe"}), encoding="utf-8")
    artifact_hashes = {key: _sha_file(path) for key, path in paths.items()}
    manifest_sha = "unit-dataset-manifest-sha"
    manifest = {
        "schema_version": 1,
        "lineage_schema_version": 1,
        "run_id": run_id,
        "manifest_sha": manifest_sha,
        "artifact_kind": "daily_close_slot_dataset",
        "artifact_dir": str(out),
        "status": "WATCH_RESEARCH_ONLY",
        "readiness_status": "WATCH_RESEARCH_ONLY",
        "promotion_allowed": False,
        "model_build_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
        "profitability_claim_allowed": False,
        "go_summary_allowed": False,
        "round_trip_cost_bp": 23,
        "cost_sensitivity_bp": [0, 23, 46],
        "split_policy": {
            "method": "chronological_train_val_test_with_purge_embargo",
            "purge_days": 1,
            "embargo_days": 1,
        },
        "slot_count": 10,
        "total_capital_krw": 1_000_000,
        "price_basis": "unknown",
        "price_basis_status": "UNKNOWN_CONFIRMED",
        "decision_grade_return_status": "BLOCKED_UNTIL_PRICE_BASIS_VERIFIED",
        "upstream_gate_blockers": ["D0_PRICE_BASIS_NOT_VERIFIED"],
        "fill_mode": "close_to_next_close_research_label",
        "execution_realism": "non_executable_upper_bound_without_preclose_features",
        "feature_columns": ["feature_a", "candidate_score_causal_momentum"],
        "artifacts": {key: str(path) for key, path in paths.items()},
        "artifact_hashes": artifact_hashes,
        "row_counts": {
            "close_slot_panel_rows": len(panel_rows),
            "candidate_score_rows": len(panel_rows),
            "label_audit_rows": len(panel_rows),
        },
        "source_run_ids": {"daily_db_fingerprint": "unit-db", "universe_manifest_sha": "unit-universe"},
        "lineage_validation_status": "PASS",
        "lineage_validation_errors": [],
    }
    manifest_path = out / "close_slot_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"root": root, "run_id": run_id, "manifest_sha": manifest_sha, "manifest_path": manifest_path, "panel_rows": panel_rows}


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def test_load_requires_explicit_dataset_run_id_hash_and_lineage(tmp_path: Path):
    dataset = _write_dataset_run(tmp_path / "dataset_root")

    loaded = load_close_slot_dataset_run(
        dataset_artifact_root=dataset["root"],
        dataset_run_id=dataset["run_id"],
        dataset_manifest_sha=dataset["manifest_sha"],
    )

    assert loaded["manifest"]["run_id"] == "dataset_unit"
    assert loaded["panel_rows"][0]["code"] == "000001"
    with pytest.raises(ValueError, match="dataset_manifest_sha"):
        load_close_slot_dataset_run(dataset_artifact_root=dataset["root"], dataset_run_id=dataset["run_id"], dataset_manifest_sha="")
    with pytest.raises(ValueError, match="sha mismatch"):
        load_close_slot_dataset_run(dataset_artifact_root=dataset["root"], dataset_run_id=dataset["run_id"], dataset_manifest_sha="wrong")
    with pytest.raises(ValueError, match="unsafe run_id"):
        load_close_slot_dataset_run(dataset_artifact_root=dataset["root"], dataset_run_id="..", dataset_manifest_sha=dataset["manifest_sha"])


def test_run_close_slot_training_emits_required_baselines_and_no_oos_fit(tmp_path: Path):
    dataset = _write_dataset_run(tmp_path / "dataset_root")
    config = CloseSlotTrainConfig(
        dataset_run_id=dataset["run_id"],
        dataset_manifest_sha=dataset["manifest_sha"],
        dataset_artifact_root=dataset["root"],
        output_root=tmp_path / "train_root",
        run_id="train_unit",
        total_capital_krw=1_000_000,
        seed=7,
        min_fit_dates=1,
        replay_window_dates=1,
        freeze_cadence_dates=1,
    )

    result = run_close_slot_training(config)
    manifest = result["manifest"]

    assert manifest["source_run_ids"] == {
        "dataset_run_id": "dataset_unit",
        "dataset_manifest_sha": "unit-dataset-manifest-sha",
    }
    assert manifest["promotion_allowed"] is False
    assert manifest["model_build_allowed"] is False
    assert manifest["live_broker_order_allowed"] is False
    assert manifest["profitability_claim_allowed"] is False
    assert manifest["paper_forward_allowed"] is False
    assert manifest["go_summary_allowed"] is False
    assert manifest["round_trip_cost_bp"] == 23
    assert manifest["schema_version"] == 2
    assert manifest["primary_cost_scenario_id"] == "base_23bp"
    assert manifest["cost_model_schema_version"] == 2
    assert manifest["shuffle_baseline_only"] is True
    assert manifest["replay_mode_id"] == "expanding_train_replay_reward_weighted_refit_v1"
    assert manifest["walk_forward_config"]["oos_rows_used_for_fit"] == 0
    assert manifest["cost_sensitivity_bp"] == [0, 23, 46]
    assert manifest["policy_score_contract"]["audit_fields"] == [
        "dataset_manifest_sha",
        "dataset_run_id",
        "decision_grade_return_status",
        "execution_realism",
        "fill_mode",
        "price_basis_status",
        "primary_cost_scenario_id",
        "round_trip_cost_bp",
        "upstream_gate_blockers",
    ]
    assert manifest["train_only_fit"] is True
    assert manifest["validation_test_no_retune"] is True
    assert manifest["fit_summary"]["train_rows"] == 4
    assert manifest["fit_summary"]["oos_rows_used_for_fit"] == 0
    assert manifest["fit_summary"]["feedback_weighted_refit_used"] is True
    assert manifest["fit_summary"]["feedback_weighted_train_rows"] > 0
    assert manifest["threshold_selection"]["split"] == "train"
    assert manifest["threshold_selection"]["oos_rows_used_for_fit"] == 0
    assert manifest["threshold_selection"]["threshold_text"] == manifest["fit_summary"]["threshold_text"]
    assert set(manifest["required_baselines"]) == {
        "no_trade_control",
        "deterministic_shuffle_top10_control",
        "momentum_top10_score_and_pick",
        "contextual_bandit_linear_train_only_score_and_pick",
    }

    summaries = {row["policy"]: row for row in manifest["summary"]}
    assert summaries["no_trade_control"]["filled_slots"] == 0
    assert summaries["no_trade_control"]["total_net_pnl_krw"] == 0.0
    assert summaries["contextual_bandit_linear_train_only_score_and_pick"]["filled_slots"] > 0
    assert summaries["deterministic_shuffle_top10_control"]["shuffle_baseline_only"] is True
    assert summaries["deterministic_shuffle_top10_control"]["policy_action_allowed"] is False
    assert summaries["contextual_bandit_linear_train_only_score_and_pick"]["oos_rows_used_for_fit"] == 0
    score_rows = _read_csv(Path(result["paths"]["policy_scores"]))
    assert {row["policy"] for row in score_rows} >= set(manifest["required_baselines"])
    assert "000001" in {row["code"] for row in score_rows}
    assert {row["dataset_run_id"] for row in score_rows} == {"dataset_unit"}
    assert {row["dataset_manifest_sha"] for row in score_rows} == {"unit-dataset-manifest-sha"}
    assert {row["price_basis_status"] for row in score_rows} == {"UNKNOWN_CONFIRMED"}
    assert {row["decision_grade_return_status"] for row in score_rows} == {"BLOCKED_UNTIL_PRICE_BASIS_VERIFIED"}
    assert {row["round_trip_cost_bp"] for row in score_rows} == {"23"}
    assert {row["primary_cost_scenario_id"] for row in score_rows} == {"base_23bp"}
    contextual_rows = [row for row in score_rows if row["policy"] == "contextual_bandit_linear_train_only_score_and_pick"]
    assert {row["threshold"] for row in contextual_rows} == {manifest["threshold_selection"]["threshold_text"]}
    assert {row["cost_scenario_id"] for row in contextual_rows} == {"base_23bp"}
    assert {row["lineage"] for row in contextual_rows} == {"primary_train_threshold_frozen_replay"}
    shuffle_rows = [row for row in score_rows if row["policy"] == "deterministic_shuffle_top10_control"]
    assert {row["policy_action_allowed"] for row in shuffle_rows} == {"False"}
    assert {"selected", "selection_reason", "selected_count", "hold_cash_count", "slot_state_feedback"} <= set(score_rows[0])
    threshold_rows = _read_csv(Path(result["paths"]["threshold_search"]))
    assert any(row["chosen"] == "True" for row in threshold_rows)
    assert {row["split"] for row in threshold_rows} == {"train"}
    assert {row["oos_rows_used_for_fit"] for row in threshold_rows} == {"0"}
    windows = json.loads(Path(result["paths"]["walk_forward_windows"]).read_text(encoding="utf-8"))
    assert windows["mode_id"] == "expanding_train_replay_reward_weighted_refit_v1"
    assert windows["oos_rows_used_for_fit"] == 0
    assert all(window["oos_rows_used_for_fit"] == 0 for window in windows["windows"])
    assert windows["windows"][1]["feedback_source_split"] == "none_frozen_held_out"
    assert windows["feedback_weighted_refit"]["feedback_weighted_train_rows"] > 0
    assert all(window["feedback_weighted_refit_used"] is True for window in windows["windows"])
    train_window_ids = {
        window["window_id"]
        for window in windows["windows"]
        if str(window["window_id"]).startswith("train_replay_refit_")
    }
    threshold_train_window_ids = {
        row["window_id"]
        for row in threshold_rows
        if row["window_id"].startswith("train_replay_refit_")
    }
    assert threshold_train_window_ids <= train_window_ids
    date_ledgers = json.loads(Path(result["paths"]["date_ledgers"]).read_text(encoding="utf-8"))
    assert {ledger["action_label"] for ledger in date_ledgers["deterministic_shuffle_top10_control"]} == {
        "selected_code_replay_adapter_only_not_policy_action"
    }
    replay = json.loads(Path(result["paths"]["replay_episode_ledgers"]).read_text(encoding="utf-8"))
    assert all(episode["oos_rows_used_for_fit"] == 0 for episode in replay["episodes"])
    assert all(
        feedback["feedback_used_for_fit"] is False
        for episode in replay["episodes"]
        if episode["replay_split"] in {"val", "test"}
        for feedback in episode["slot_feedback"]
    )
    assert any(
        feedback["feedback_used_for_fit"] is True
        for episode in replay["episodes"]
        if episode["replay_split"] == "train"
        for feedback in episode["slot_feedback"]
    )
    cost_rows = _read_csv(Path(result["paths"]["cost_scenario_summary"]))
    assert {"zero_control_0bp", "base_23bp", "stress_46bp"} <= {row["cost_scenario_id"] for row in cost_rows}
    zero_rows = [row for row in cost_rows if row["cost_scenario_id"] == "zero_control_0bp"]
    assert all(float(row["sell_tax_bp"]) == 0.0 for row in zero_rows)
    stress_rows = [row for row in cost_rows if row["cost_scenario_id"] == "stress_46bp"]
    assert all(float(row["buy_slippage_bp"]) == 11.5 and float(row["sell_slippage_bp"]) == 11.5 for row in stress_rows)

    repeat = run_close_slot_training(
        CloseSlotTrainConfig(
            dataset_run_id=dataset["run_id"],
            dataset_manifest_sha=dataset["manifest_sha"],
            dataset_artifact_root=dataset["root"],
            output_root=tmp_path / "train_root",
            run_id="train_unit_repeat",
            total_capital_krw=1_000_000,
            seed=7,
        )
    )
    first_shuffle = [row for row in _read_csv(Path(result["paths"]["policy_scores"])) if row["policy"] == "deterministic_shuffle_top10_control"]
    second_shuffle = [row for row in _read_csv(Path(repeat["paths"]["policy_scores"])) if row["policy"] == "deterministic_shuffle_top10_control"]
    assert [(row["date"], row["code"], row["score"]) for row in first_shuffle] == [
        (row["date"], row["code"], row["score"]) for row in second_shuffle
    ]
    with pytest.raises(FileExistsError):
        run_close_slot_training(config)
    with pytest.raises(ValueError, match="primary cost must remain 23bp"):
        run_close_slot_training(
            CloseSlotTrainConfig(
                dataset_run_id=dataset["run_id"],
                dataset_manifest_sha=dataset["manifest_sha"],
                dataset_artifact_root=dataset["root"],
                output_root=tmp_path / "train_root",
                run_id="bad_cost",
                total_capital_krw=1_000_000,
                cost_bp=46,
            )
        )


def test_frozen_d3_scores_are_reledgered_through_close_slot_accounting(tmp_path: Path):
    dataset = _write_dataset_run(tmp_path / "dataset_root")
    d3_path = tmp_path / "frozen_d3_scores.csv"
    _write_csv(
        d3_path,
        [
            {"date": "2024-04-04", "code": "000001", "score": 0.9, "selected": True},
            {"date": "2024-04-04", "code": "000002", "score": 0.1, "selected": False},
        ],
        ["date", "code", "score", "selected"],
    )

    result = run_close_slot_training(
        CloseSlotTrainConfig(
            dataset_run_id=dataset["run_id"],
            dataset_manifest_sha=dataset["manifest_sha"],
            dataset_artifact_root=dataset["root"],
            output_root=tmp_path / "train_root",
            run_id="train_with_d3",
            total_capital_krw=1_000_000,
            frozen_d3_score_path=d3_path,
        )
    )

    manifest = result["manifest"]
    assert manifest["d3_comparator"] == {
        "present": True,
        "reledgered_through_close_slot_accounting": True,
        "source_score_path": str(d3_path),
    }
    summaries = {row["policy"]: row for row in manifest["summary"]}
    assert "frozen_d3_reledgered_score_and_pick" in summaries
    assert result["policies"]["frozen_d3_reledgered_score_and_pick"]["reledgered_through_close_slot_accounting"] is True
    assert result["policies"]["frozen_d3_reledgered_score_and_pick"]["date_ledgers"][2]["action_label"] == "selected_code_replay_adapter_only_not_policy_action"
    d3_cost_rows = _read_csv(Path(result["paths"]["cost_scenario_summary"]))
    d3_test_rows = [
        row
        for row in d3_cost_rows
        if row["policy"] == "frozen_d3_reledgered_score_and_pick"
        and row["split"] == "test"
        and row["cost_scenario_id"] == "base_23bp"
    ]
    assert d3_test_rows
    assert int(d3_test_rows[0]["selected_count"]) == 1
    empty_d3_path = tmp_path / "empty_frozen_d3_scores.csv"
    _write_csv(
        empty_d3_path,
        [
            {"date": "2024-04-04", "code": "000001", "score": 0.9, "selected": False},
            {"date": "2024-04-04", "code": "000002", "score": 0.1, "selected": False},
        ],
        ["date", "code", "score", "selected"],
    )
    empty_result = run_close_slot_training(
        CloseSlotTrainConfig(
            dataset_run_id=dataset["run_id"],
            dataset_manifest_sha=dataset["manifest_sha"],
            dataset_artifact_root=dataset["root"],
            output_root=tmp_path / "train_root",
            run_id="train_with_empty_d3",
            total_capital_krw=1_000_000,
            frozen_d3_score_path=empty_d3_path,
        )
    )
    empty_d3_ledgers = empty_result["policies"]["frozen_d3_reledgered_score_and_pick"]["date_ledgers"]
    assert all(int(ledger["selected_count"]) == 0 for ledger in empty_d3_ledgers)
    assert {ledger["action_label"] for ledger in empty_d3_ledgers} == {
        "selected_code_replay_adapter_only_not_policy_action"
    }


def test_normalization_and_diagnostics_surfaced(tmp_path: Path):
    dataset = _write_dataset_run(tmp_path / "dataset_root")
    result = run_close_slot_training(
        CloseSlotTrainConfig(
            dataset_run_id=dataset["run_id"],
            dataset_manifest_sha=dataset["manifest_sha"],
            dataset_artifact_root=dataset["root"],
            output_root=tmp_path / "train_root",
            run_id="train_norm",
            total_capital_krw=1_000_000,
            seed=7,
        )
    )
    manifest = result["manifest"]
    fit_summary = manifest["fit_summary"]

    # Scaler provenance surfaced; weights are now a model dict, not a bare map.
    assert fit_summary["feature_standardized"] is True
    assert fit_summary["fit_method"] == "train_only_zscore_covariance_l1_v1"
    assert "chosen_is_no_trade_sentinel" in fit_summary
    weights_model = fit_summary["weights"]
    assert {"weights", "feature_mean", "feature_std", "fit_method"} <= set(weights_model)

    # Forced top-10 diagnostic exposed both in the manifest and the summary rows.
    diagnostic = manifest["forced_top10_diagnostic"]
    assert diagnostic["policy"] == "contextual_bandit_linear_top10_forced_diagnostic"
    summaries = {row["policy"]: row for row in manifest["summary"]}
    assert "contextual_bandit_linear_top10_forced_diagnostic" in summaries
    assert summaries["contextual_bandit_linear_top10_forced_diagnostic"]["policy_action_allowed"] is False

    # Guardrails unchanged.
    assert manifest["model_build_allowed"] is False
    assert manifest["profitability_claim_allowed"] is False
