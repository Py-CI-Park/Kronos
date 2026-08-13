from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from stom_rl.daily_market_allocation_artifacts import (
    VALIDATION_ACTION_LEDGER_FILE,
    VALIDATION_RECEIPT_FILE,
)
from stom_rl.daily_market_allocation_experiment import planned_allocation_arms
from stom_rl.daily_market_allocation_input_snapshot import (
    immutable_allocation_direct_inputs,
)
from stom_rl.daily_market_allocation_rl_contract import (
    ALLOCATION_MODEL_SEEDS,
    AllocationAlgorithm,
)
from stom_rl.daily_market_allocation_runner import DailyMarketAllocationPaths
from stom_rl.daily_market_allocation_runner import (
    assert_allocation_inputs_unchanged,
    capture_allocation_input_snapshot,
    ensure_allocation_output_available,
    immutable_allocation_database_snapshot,
    load_allocation_direct_datasets,
)
from stom_rl.daily_market_rl_contract import DailyMarketRlContractError
from stom_rl.daily_market_state_dataset import CAUSAL_FEATURE_COLUMNS


def _write_direct_inputs(paths: DailyMarketAllocationPaths) -> None:
    for index, path in enumerate(
        (
            paths.candidate_scores,
            paths.source_manifest,
            paths.causal_panel,
            paths.authority_receipt,
            paths.source_allocation_receipt,
        ),
        start=1,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_bytes(f"direct-input-{index}".encode())


def _write_loadable_direct_inputs(paths: DailyMarketAllocationPaths) -> None:
    for path in (
        paths.candidate_scores,
        paths.source_manifest,
        paths.causal_panel,
        paths.authority_receipt,
        paths.source_allocation_receipt,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
    _ = paths.source_manifest.write_text(
        json.dumps(
            {
                "fill_mode": "close_to_next_close_research_label",
                "price_basis": "unknown",
                "decision_grade_return_status": ("BLOCKED_UNTIL_PRICE_BASIS_VERIFIED"),
                "promotion_allowed": False,
            }
        ),
        encoding="utf-8",
    )
    score_fields = (
        "date",
        "table",
        "code",
        "score",
        "split",
        "eligible_for_selection",
    )
    with paths.candidate_scores.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=score_fields)
        writer.writeheader()
        for index in range(10):
            code = f"{index + 1:06d}"
            writer.writerow(
                {
                    "date": "20260102",
                    "table": f"A{code}",
                    "code": code,
                    "score": str(10 - index),
                    "split": "TRAIN",
                    "eligible_for_selection": "1",
                }
            )
    panel_fields = (
        "date",
        "table",
        "code",
        "split",
        *CAUSAL_FEATURE_COLUMNS,
    )
    with paths.causal_panel.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=panel_fields)
        writer.writeheader()
        for index in range(10):
            code = f"{index + 1:06d}"
            writer.writerow(
                {
                    "date": "20260102",
                    "table": f"A{code}",
                    "code": code,
                    "split": "TRAIN",
                    **{feature: str(index + 1) for feature in CAUSAL_FEATURE_COLUMNS},
                }
            )
    _ = paths.authority_receipt.write_text("{}", encoding="utf-8")
    _ = paths.source_allocation_receipt.write_text("{}", encoding="utf-8")


def test_allocation_plan_contains_dqn_and_cql_five_seed_arms() -> None:
    # Given/When: the preregistered multi-action model plan is expanded.
    arms = planned_allocation_arms()

    # Then: exactly ten models are fixed before any validation execution.
    assert len(arms) == 10
    assert {
        algorithm: tuple(row.seed for row in arms if row.algorithm is algorithm)
        for algorithm in AllocationAlgorithm
    } == {algorithm: ALLOCATION_MODEL_SEEDS for algorithm in AllocationAlgorithm}


def test_registered_allocation_paths_never_point_at_test_or_fresh_data(
    tmp_path: Path,
) -> None:
    # Given/When: one repository root is registered.
    paths = DailyMarketAllocationPaths.registered(tmp_path)

    # Then: sources, authority receipt, and generated screen have fixed locations.
    dataset = (
        tmp_path
        / "webui"
        / "rl_runs"
        / "daily_close_slot_dataset"
        / "daily_close_slot_research_dataset_2026_07_03"
    )
    assert paths.candidate_scores == dataset / "candidate_score_rows.csv"
    assert paths.causal_panel == dataset / "close_slot_panel.csv"
    assert paths.stockinfo_database == tmp_path / "_database" / "stock_tick_back.db"
    assert (
        paths.source_artifact_root
        == tmp_path / "_database" / "market_authority_sources"
    )
    assert paths.authority_receipt.name == "authority_receipt.json"
    assert paths.source_allocation_receipt.name == "validation_receipt.json"
    assert (
        paths.output_directory.name == "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002"
    )


def test_allocation_evidence_names_match_the_immutable_preregistration() -> None:
    assert VALIDATION_RECEIPT_FILE == "validation_receipt.json"
    assert VALIDATION_ACTION_LEDGER_FILE == "validation_action_ledger.jsonl"


def test_allocation_input_snapshot_detects_concurrent_mutation(tmp_path: Path) -> None:
    paths = DailyMarketAllocationPaths.registered(tmp_path)
    direct_inputs = (
        paths.candidate_scores,
        paths.source_manifest,
        paths.causal_panel,
        paths.daily_database,
        paths.authority_receipt,
        paths.source_allocation_receipt,
    )
    for index, path in enumerate(direct_inputs, start=1):
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_bytes(f"input-{index}".encode())
    snapshot = capture_allocation_input_snapshot(paths)

    _ = paths.candidate_scores.write_bytes(b"mutated-after-snapshot")

    with pytest.raises(
        DailyMarketRlContractError,
        match="ALLOCATION_INPUT_CHANGED_DURING_RUN",
    ):
        assert_allocation_inputs_unchanged(paths, snapshot)


def test_allocation_direct_snapshot_closes_original_path_aba(tmp_path: Path) -> None:
    paths = DailyMarketAllocationPaths.registered(tmp_path)
    _write_direct_inputs(paths)
    expected = capture_allocation_input_snapshot(paths)
    original = paths.candidate_scores.read_bytes()

    with immutable_allocation_direct_inputs(paths, expected) as frozen:
        assert frozen.candidate_scores != paths.candidate_scores
        assert frozen.candidate_scores.read_bytes() == original
        _ = paths.candidate_scores.write_bytes(b"temporary-aba-payload")
        _ = paths.candidate_scores.write_bytes(original)
        assert frozen.candidate_scores.read_bytes() == original

    assert_allocation_inputs_unchanged(paths, expected)
    assert not (paths.output_directory / "_direct_input_snapshot").exists()


def test_allocation_direct_snapshot_detects_snapshot_tamper(tmp_path: Path) -> None:
    paths = DailyMarketAllocationPaths.registered(tmp_path)
    _write_direct_inputs(paths)
    expected = capture_allocation_input_snapshot(paths)

    with pytest.raises(
        DailyMarketRlContractError,
        match="ALLOCATION_INPUT_SNAPSHOT_CHANGED_DURING_RUN",
    ):
        with immutable_allocation_direct_inputs(paths, expected) as frozen:
            _ = frozen.candidate_scores.write_bytes(b"tampered-snapshot")

    assert not (paths.output_directory / "_direct_input_snapshot").exists()


def test_allocation_loads_score_and_panel_from_one_snapshot_root(
    tmp_path: Path,
) -> None:
    paths = DailyMarketAllocationPaths.registered(tmp_path)
    _write_loadable_direct_inputs(paths)
    expected = capture_allocation_input_snapshot(paths)

    with immutable_allocation_direct_inputs(paths, expected) as frozen:
        scores, states = load_allocation_direct_datasets(frozen)

    assert scores.day_count == 1
    assert scores.selected_score_count == 10
    assert states.day_count == 1
    assert states.feature_vector_size == 160


def test_registered_output_refuses_an_existing_run(tmp_path: Path) -> None:
    output = tmp_path / "run"
    output.mkdir()
    _ = (output / "summary.json").write_text("{}", encoding="utf-8")

    with pytest.raises(
        DailyMarketRlContractError,
        match="ALLOCATION_OUTPUT_ALREADY_EXISTS",
    ):
        ensure_allocation_output_available(output)


def test_allocation_reads_an_isolated_database_snapshot(tmp_path: Path) -> None:
    paths = DailyMarketAllocationPaths.registered(tmp_path)
    paths.daily_database.parent.mkdir(parents=True)
    payload = b"immutable-database-fixture"
    _ = paths.daily_database.write_bytes(payload)
    expected_hash = hashlib.sha256(payload).hexdigest()

    with immutable_allocation_database_snapshot(paths, expected_hash) as snapshot:
        assert snapshot != paths.daily_database
        assert snapshot.read_bytes() == payload
        assert snapshot.is_file()

    assert not (paths.output_directory / "_input_snapshot").exists()


def test_allocation_rejects_a_snapshot_changed_during_training(tmp_path: Path) -> None:
    paths = DailyMarketAllocationPaths.registered(tmp_path)
    paths.daily_database.parent.mkdir(parents=True)
    payload = b"immutable-database-fixture"
    _ = paths.daily_database.write_bytes(payload)
    expected_hash = hashlib.sha256(payload).hexdigest()

    with pytest.raises(
        DailyMarketRlContractError,
        match="ALLOCATION_DATABASE_SNAPSHOT_CHANGED_DURING_RUN",
    ):
        with immutable_allocation_database_snapshot(paths, expected_hash) as snapshot:
            _ = snapshot.write_bytes(b"tampered-during-training")

    assert not (paths.output_directory / "_input_snapshot").exists()
