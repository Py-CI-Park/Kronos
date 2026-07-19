import csv
import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl.daily_ohlcv_db import EXPECTED_COLUMNS  # noqa: E402
from stom_rl.daily_close_slot_dataset import (  # noqa: E402
    COST_SENSITIVITY_BP,
    COST_MODEL_SCHEMA_VERSION,
    COST_SCENARIOS,
    HOLD_CASH_ACTION,
    MAX_SLOT_COUNT,
    ROUND_TRIP_COST_BP,
    SELECTION_CARDINALITY,
    build_daily_close_slot_dataset,
    validate_close_slot_dataset_lineage,
    write_close_slot_dataset_artifacts,
)


def _create_daily_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    cols = ", ".join([f'"{col}" REAL' for col in EXPECTED_COLUMNS if col != "date"])
    for table in ("A000250", "A005930", "A069500"):
        conn.execute(f'CREATE TABLE "{table}" ("date" TEXT, {cols})')

    rows_000250 = []
    rows_005930 = []
    rows_etf = []
    for index in range(8):
        date = f"2024-02-{index + 1:02d}"
        close_000250 = 100.0 + index
        close_005930 = 200.0 + index * 2
        rows_000250.append(
            (
                date,
                close_000250 - 0.5,
                close_000250 + 1.0,
                close_000250 - 1.0,
                close_000250,
                1000.0 + index * 10,
                10,
                0,
                0,
                1.5 + index,
                100.0 + index,
                100.0 + index,
            )
        )
        rows_005930.append(
            (
                date,
                close_005930 - 1.0,
                close_005930 + 2.0,
                close_005930 - 2.0,
                close_005930,
                2000.0 + index * 20,
                10,
                0,
                0,
                2.0 + index,
                200.0 + index,
                200.0 + index,
            )
        )
        rows_etf.append((date, 50.0, 51.0, 49.0, 50.0, 500.0, 10, 0, 0, 0, 0, 0))
    conn.executemany('INSERT INTO "A000250" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', rows_000250)
    conn.executemany('INSERT INTO "A005930" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', rows_005930)
    conn.executemany('INSERT INTO "A069500" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', rows_etf)
    conn.commit()
    conn.close()
    return path


def _create_universe_manifest(path: Path) -> Path:
    manifest = {
        "schema_version": 1,
        "manifest_sha": "unit-close-slot-universe-sha",
        "review_status": "WATCH_REQUIRES_OFFICIAL_OR_MANUAL_REVIEW",
        "verdict": "WATCH_HEURISTIC_UNIVERSE",
        "symbols": [
            {"table": "A000250", "code": "000250", "name": "삼천당제약", "include": True},
            {"table": "A005930", "code": "005930", "name": "삼성전자", "include": True},
            {
                "table": "A069500",
                "code": "069500",
                "name": "KODEX 200",
                "include": False,
                "exclusion_reason": "ETF_ETN_FUND_NAME_PREFIX",
            },
        ],
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return path


def test_build_close_slot_dataset_preserves_guardrails_codes_and_missing_labels(tmp_path: Path):
    db_path = _create_daily_db(tmp_path / "daily.db")
    universe_path = _create_universe_manifest(tmp_path / "universe.json")

    dataset = build_daily_close_slot_dataset(
        daily_db_path=db_path,
        universe_manifest_path=universe_path,
        train_fraction=0.5,
        val_fraction=0.25,
        purge_days=0,
        embargo_days=0,
        total_capital_krw=10_000_000,
    )

    manifest = dataset["manifest"]
    assert manifest["artifact_generation_allowed"] is True
    assert manifest["promotion_allowed"] is False
    assert manifest["model_build_allowed"] is False
    assert manifest["paper_forward_allowed"] is False
    assert manifest["live_broker_order_allowed"] is False
    assert manifest["profitability_claim_allowed"] is False
    assert manifest["go_summary_allowed"] is False
    assert manifest["price_basis"] == "unknown"
    assert manifest["price_basis_status"] == "UNKNOWN_CONFIRMED"
    assert manifest["decision_grade_return_status"] == "BLOCKED_UNTIL_PRICE_BASIS_VERIFIED"
    assert manifest["universe_verdict"] == "WATCH_HEURISTIC_UNIVERSE"
    assert manifest["upstream_gate_blockers"] == [
        "D0_PRICE_BASIS_NOT_VERIFIED",
        "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED",
    ]
    assert manifest["schema_version"] == 2
    assert manifest["daily_db_access"] == {
        "access_mode": "read_only",
        "sqlite_uri_mode": "ro",
        "pragma_query_only": True,
        "mutation_allowed": False,
        "connection_helper": "stom_rl.daily_ohlcv_db.connect_readonly",
    }
    assert manifest["cost_model_schema_version"] == COST_MODEL_SCHEMA_VERSION
    assert manifest["max_slot_count"] == MAX_SLOT_COUNT
    assert manifest["selection_cardinality"] == SELECTION_CARDINALITY
    assert manifest["hold_cash_action"] is HOLD_CASH_ACTION
    assert manifest["cost_scenarios"] == COST_SCENARIOS
    assert manifest["cost_scenarios"]["base_23bp"] == {
        "scenario_id": "base_23bp",
        "sell_tax_bp": 20.0,
        "buy_commission_bp": 1.5,
        "sell_commission_bp": 1.5,
        "buy_slippage_bp": 0.0,
        "sell_slippage_bp": 0.0,
        "total_bp": 23.0,
    }
    assert manifest["cost_scenarios"]["stress_46bp"]["buy_slippage_bp"] == 11.5
    assert manifest["policy_threshold_contract"]["threshold_inclusive"] is True
    assert manifest["policy_threshold_contract"]["selection_cardinality"] == SELECTION_CARDINALITY
    assert manifest["false_locks"]["promotion_allowed"] is False
    assert manifest["d0_d1_blockers"] == {
        "d0_price_basis_blocked": True,
        "d1_universe_blocked": True,
        "active_blockers": [
            "D0_PRICE_BASIS_NOT_VERIFIED",
            "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED",
        ],
    }
    assert manifest["fill_mode"] == "close_to_next_close_research_label"
    assert manifest["execution_realism"] == "non_executable_upper_bound_without_preclose_features"
    assert manifest["round_trip_cost_bp"] == ROUND_TRIP_COST_BP
    assert manifest["cost_sensitivity_bp"] == COST_SENSITIVITY_BP
    assert manifest["slot_count"] == 10
    assert manifest["total_capital_krw"] == 10_000_000
    assert manifest["source_run_ids"]["universe_manifest_sha"] == "unit-close-slot-universe-sha"
    assert manifest["row_counts"]["close_slot_panel_rows"] == 16
    assert manifest["row_counts"]["label_audit_rows"] == 16

    codes = {row["code"] for row in dataset["close_slot_panel"]}
    assert "000250" in codes
    assert "005930" in codes
    assert "069500" not in codes
    assert all(isinstance(row["code"], str) and len(row["code"]) == 6 for row in dataset["close_slot_panel"])

    final_rows = [row for row in dataset["close_slot_panel"] if row["date"] == "2024-02-08"]
    assert final_rows
    assert all(row["next_close"] is None for row in final_rows)
    assert all(row["blocked_reason"] == "MISSING_NEXT_CLOSE" for row in final_rows)
    assert all(row["eligible_for_selection"] is False for row in final_rows)

    schema = dataset["candidate_scores_input_schema"]
    assert schema["selected_code_lists"] == "test_or_replay_adapter_only_not_policy_action"
    assert schema["canonical_sort"][0] == {"column": "score", "direction": "desc"}
    assert schema["canonical_sort"][2] == {
        "column": "code",
        "direction": "asc",
        "format": "zero_padded_6_digit_string",
    }
    assert schema["max_slot_count"] == 10
    assert schema["selection_cardinality"] == "threshold_selected_0_to_10"
    assert schema["hold_cash_action"] is True
    assert schema["code_format"] == "zero_padded_6_digit_string_preserved"
    assert dataset["feature_contract"]["code_format"] == "zero_padded_6_digit_string_preserved"
    assert dataset["source_hashes"]["dataset_manifest_contract_sha256"]
def test_no_blocker_research_artifact_still_does_not_emit_ready_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = _create_daily_db(tmp_path / "daily.db")
    universe_path = tmp_path / "official_universe.json"
    universe_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "manifest_sha": "official-unit-universe-sha",
                "review_status": "OFFICIAL_OR_MANUAL_REVIEWED",
                "universe_review_status": "OFFICIAL_OR_MANUAL_REVIEWED",
                "verdict": "OFFICIAL_OR_MANUAL_REVIEWED",
                "symbols": [
                    {"table": "A000250", "code": "000250", "include": True},
                    {"table": "A005930", "code": "005930", "include": True},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    import stom_rl.daily_close_slot_dataset as close_slot_dataset

    monkeypatch.setattr(close_slot_dataset, "PRICE_BASIS_STATUS", "VERIFIED")
    monkeypatch.setattr(close_slot_dataset, "DECISION_GRADE_RETURN_STATUS", "VERIFIED")
    dataset = close_slot_dataset.build_daily_close_slot_dataset(
        daily_db_path=db_path,
        universe_manifest_path=universe_path,
        train_fraction=0.5,
        val_fraction=0.25,
        purge_days=0,
        embargo_days=0,
    )
    manifest = dataset["manifest"]
    assert manifest["upstream_gate_blockers"] == []
    assert manifest["status"] == "NO-GO_RESEARCH_ONLY"
    assert manifest["readiness_status"] == "NO-GO_RESEARCH_ONLY"
    assert "READY" not in manifest["status"]
    assert "READY" not in manifest["readiness_status"]
    assert manifest["promotion_allowed"] is False
    assert manifest["model_build_allowed"] is False
    assert manifest["go_summary_allowed"] is False



def test_write_close_slot_dataset_artifacts_and_lineage_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = _create_daily_db(tmp_path / "daily.db")
    universe_path = _create_universe_manifest(tmp_path / "universe.json")

    import stom_rl.daily_close_slot_dataset as close_slot_dataset

    safe_root = tmp_path / "webui" / "rl_runs" / "daily_close_slot_dataset"
    monkeypatch.setattr(close_slot_dataset, "DEFAULT_CLOSE_SLOT_DATASET_ROOT", safe_root)
    dataset = close_slot_dataset.build_daily_close_slot_dataset(
        daily_db_path=db_path,
        universe_manifest_path=universe_path,
        train_fraction=0.5,
        val_fraction=0.25,
        purge_days=0,
        embargo_days=0,
    )
    written = close_slot_dataset.write_close_slot_dataset_artifacts(dataset, run_id="close_slot_unit")

    manifest_path = Path(written["close_slot_dataset_manifest_path"])
    assert manifest_path.exists()
    assert Path(written["close_slot_panel_path"]).exists()
    assert Path(written["candidate_scores_input_schema_path"]).exists()
    assert Path(written["feature_contract_path"]).exists()
    assert Path(written["label_audit_path"]).exists()
    assert Path(written["source_hashes_path"]).exists()
    assert written["lineage_validation_status"] == "PASS"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == "close_slot_unit"
    assert manifest["lineage_schema_version"] == 1
    assert manifest["lineage_validation_status"] == "PASS"
    assert manifest["artifact_hashes"]["close_slot_panel"]
    assert manifest["row_counts"]["close_slot_panel_rows"] == 16
    assert validate_close_slot_dataset_lineage(manifest_path)["status"] == "PASS"
    legacy_v1_manifest = json.loads(json.dumps(manifest))
    legacy_v1_manifest["schema_version"] = 1
    for key in (
        "cost_model_schema_version",
        "max_slot_count",
        "selection_cardinality",
        "hold_cash_action",
        "cost_scenarios",
        "policy_threshold_contract",
    ):
        legacy_v1_manifest.pop(key, None)
    legacy_v1_lineage = validate_close_slot_dataset_lineage(legacy_v1_manifest)
    assert legacy_v1_lineage["status"] == "PASS"
    missing_schema_version = json.loads(json.dumps(manifest))
    del missing_schema_version["schema_version"]
    missing_schema_lineage = validate_close_slot_dataset_lineage(missing_schema_version)
    assert missing_schema_lineage["status"] == "BLOCK"
    assert "LINEAGE_MISSING_SCHEMA_VERSION" in missing_schema_lineage["errors"]


    missing_db_access_manifest = json.loads(json.dumps(manifest))
    del missing_db_access_manifest["daily_db_access"]
    missing_db_access_lineage = validate_close_slot_dataset_lineage(missing_db_access_manifest)
    assert missing_db_access_lineage["status"] == "BLOCK"
    assert "DATASET_V2_DB_ACCESS_NOT_READ_ONLY" in missing_db_access_lineage["errors"]
    missing_v2_cost_model = json.loads(json.dumps(manifest))
    del missing_v2_cost_model["cost_model_schema_version"]
    missing_v2_cost_model_lineage = validate_close_slot_dataset_lineage(missing_v2_cost_model)
    assert missing_v2_cost_model_lineage["status"] == "BLOCK"
    assert "DATASET_V2_COST_MODEL_SCHEMA_MISSING" in missing_v2_cost_model_lineage["errors"]

    scalar_only_v2_costs = json.loads(json.dumps(manifest))
    scalar_only_v2_costs.pop("cost_scenarios")
    scalar_only_v2_costs_lineage = validate_close_slot_dataset_lineage(scalar_only_v2_costs)
    assert scalar_only_v2_costs_lineage["status"] == "BLOCK"
    assert "DATASET_V2_COST_SCENARIOS_INVALID" in scalar_only_v2_costs_lineage["errors"]

    bad_component_v2_costs = json.loads(json.dumps(manifest))
    bad_component_v2_costs["cost_scenarios"]["base_23bp"]["sell_tax_bp"] = 0.0
    bad_component_v2_costs_lineage = validate_close_slot_dataset_lineage(bad_component_v2_costs)
    assert bad_component_v2_costs_lineage["status"] == "BLOCK"
    assert "DATASET_V2_COST_SCENARIOS_INVALID" in bad_component_v2_costs_lineage["errors"]

    bad_slot_contract = json.loads(json.dumps(manifest))
    bad_slot_contract["max_slot_count"] = 9
    bad_slot_contract["selection_cardinality"] = "exactly_10"
    bad_slot_contract["hold_cash_action"] = False
    bad_slot_contract_lineage = validate_close_slot_dataset_lineage(bad_slot_contract)
    assert bad_slot_contract_lineage["status"] == "BLOCK"
    assert "DATASET_V2_SLOT_CONTRACT_INVALID" in bad_slot_contract_lineage["errors"]

    bad_policy_contract = json.loads(json.dumps(manifest))
    bad_policy_contract["policy_threshold_contract"]["threshold_inclusive"] = False
    bad_policy_contract_lineage = validate_close_slot_dataset_lineage(bad_policy_contract)
    assert bad_policy_contract_lineage["status"] == "BLOCK"
    assert "DATASET_V2_POLICY_CONTRACT_INVALID" in bad_policy_contract_lineage["errors"]
    bad_tie_break_contract = json.loads(json.dumps(manifest))
    bad_tie_break_contract["policy_threshold_contract"]["deterministic_tie_breaks"] = [
        {"column": "code", "direction": "asc", "format": "zero_padded_6_digit_string"},
        {"column": "score", "direction": "desc"},
    ]
    bad_tie_break_lineage = validate_close_slot_dataset_lineage(bad_tie_break_contract)
    assert bad_tie_break_lineage["status"] == "BLOCK"
    assert "DATASET_V2_POLICY_CONTRACT_INVALID" in bad_tie_break_lineage["errors"]


    stale_false_lock_manifest = json.loads(json.dumps(manifest))
    stale_false_lock_manifest["false_locks"]["paper_forward_allowed"] = True
    stale_false_lock_lineage = validate_close_slot_dataset_lineage(stale_false_lock_manifest)
    assert stale_false_lock_lineage["status"] == "BLOCK"
    assert "LINEAGE_STALE_OPTIMISTIC_FLAGS" in stale_false_lock_lineage["errors"]
    missing_false_locks_manifest = json.loads(json.dumps(manifest))
    del missing_false_locks_manifest["false_locks"]
    missing_false_locks_lineage = validate_close_slot_dataset_lineage(missing_false_locks_manifest)
    assert missing_false_locks_lineage["status"] == "BLOCK"
    assert "LINEAGE_STALE_OPTIMISTIC_FLAGS" in missing_false_locks_lineage["errors"]

    missing_hash_manifest = json.loads(json.dumps(manifest))
    del missing_hash_manifest["artifact_hashes"]["close_slot_panel"]
    missing_hash_lineage = validate_close_slot_dataset_lineage(missing_hash_manifest)
    assert missing_hash_lineage["status"] == "BLOCK"
    assert "LINEAGE_MISSING_ARTIFACT_HASH" in missing_hash_lineage["errors"]

    stale_flag_manifest = json.loads(json.dumps(manifest))
    stale_flag_manifest["model_build_allowed"] = True
    stale_flag_manifest["go_summary_allowed"] = True
    stale_flag_lineage = validate_close_slot_dataset_lineage(stale_flag_manifest)
    assert stale_flag_lineage["status"] == "BLOCK"
    assert "LINEAGE_STALE_OPTIMISTIC_FLAGS" in stale_flag_lineage["errors"]

    bad_run_manifest = json.loads(json.dumps(manifest))
    bad_run_manifest["run_id"] = "."
    bad_run_lineage = validate_close_slot_dataset_lineage(bad_run_manifest)
    assert bad_run_lineage["status"] == "BLOCK"
    assert "LINEAGE_MISSING_UPSTREAM_RUN_ID" in bad_run_lineage["errors"]

    bad_count_manifest = json.loads(json.dumps(manifest))
    bad_count_manifest["row_counts"]["close_slot_panel_rows"] = 999
    bad_count_lineage = validate_close_slot_dataset_lineage(bad_count_manifest)
    assert bad_count_lineage["status"] == "BLOCK"
    assert "LINEAGE_ROW_COUNT_MISMATCH" in bad_count_lineage["errors"]


    with Path(written["close_slot_panel_path"]).open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tampered"])
    lineage = validate_close_slot_dataset_lineage(manifest_path)
    assert lineage["status"] == "BLOCK"
    assert "LINEAGE_HASH_MISMATCH" in lineage["errors"]

    with pytest.raises(FileExistsError):
        close_slot_dataset.write_close_slot_dataset_artifacts(dataset, run_id="close_slot_unit")
    with pytest.raises(ValueError):
        close_slot_dataset.write_close_slot_dataset_artifacts(dataset, run_id="..")
    with pytest.raises(ValueError):
        close_slot_dataset.write_close_slot_dataset_artifacts(dataset, run_id=".")
    with pytest.raises(ValueError):
        close_slot_dataset.write_close_slot_dataset_artifacts(
            dataset,
            artifact_root=tmp_path / "outside_daily_close_slot_dataset",
            run_id="bad_root",
        )


def test_manifest_contract_payloads_do_not_mutate_canonical_constants(tmp_path: Path):
    db_path = _create_daily_db(tmp_path / "daily.db")
    universe_path = _create_universe_manifest(tmp_path / "universe.json")
    dataset = build_daily_close_slot_dataset(
        daily_db_path=db_path,
        universe_manifest_path=universe_path,
        train_fraction=0.5,
        val_fraction=0.25,
        purge_days=0,
        embargo_days=0,
    )

    dataset["manifest"]["cost_scenarios"]["base_23bp"]["sell_tax_bp"] = 0.0
    dataset["manifest"]["policy_threshold_contract"]["deterministic_tie_breaks"] = []
    rebuilt = build_daily_close_slot_dataset(
        daily_db_path=db_path,
        universe_manifest_path=universe_path,
        train_fraction=0.5,
        val_fraction=0.25,
        purge_days=0,
        embargo_days=0,
    )

    assert COST_SCENARIOS["base_23bp"]["sell_tax_bp"] == 20.0
    assert rebuilt["manifest"]["cost_scenarios"]["base_23bp"]["sell_tax_bp"] == 20.0
    assert rebuilt["manifest"]["policy_threshold_contract"]["deterministic_tie_breaks"]
