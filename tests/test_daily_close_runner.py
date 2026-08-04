from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from stom_rl.daily_close_research.contracts import ExecutionEvidence
from stom_rl.daily_close_research.runner import ResearchRunConfig, run_research, write_research_receipt


def _database(path: Path) -> Path:
    with sqlite3.connect(path) as connection:
        for code, growth in (("000250", 1.006), ("000660", 0.999)):
            connection.execute(
                f'CREATE TABLE "A{code}" (date INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL)'
            )
            rows = tuple(
                (
                    20250000 + index,
                    100.0 * growth**index,
                    102.0 * growth**index,
                    99.0 * growth**index,
                    101.0 * growth**index,
                    1_000_000.0 + index,
                )
                for index in range(90)
            )
            connection.executemany(f'INSERT INTO "A{code}" VALUES (?, ?, ?, ?, ?, ?)', rows)
    return path


def test_runner_creates_fail_closed_receipt_and_calibration_model(tmp_path: Path) -> None:
    config = ResearchRunConfig(
        database=_database(tmp_path / "daily.db"),
        codes=("000250", "000660"),
        output_directory=tmp_path / "output",
        seeds=(0,),
        calibration_epochs=20,
        execution_evidence=ExecutionEvidence.unverified(),
    )

    receipt = run_research(config)

    assert "NO_GO_DATA_CUSTODY" in receipt.overall_verdict
    assert receipt.economic_model_created is False
    assert receipt.calibration_model_created is True
    assert Path(receipt.calibration_model_path).is_file()
    assert receipt.stock_round_trip_cost_percent == pytest.approx(0.230)


def test_runner_binds_source_sha_without_inventing_external_custody(tmp_path: Path) -> None:
    database = _database(tmp_path / "daily.db")
    config = ResearchRunConfig(
        database=database,
        codes=("000250", "000660"),
        output_directory=tmp_path / "output",
        seeds=(0,),
        calibration_epochs=10,
        execution_evidence=ExecutionEvidence.unverified(),
    )

    receipt = run_research(config)

    assert len(receipt.source_custody.database_sha256) == 64
    assert receipt.source_custody.database_size_bytes == database.stat().st_size
    assert receipt.source_custody.requested_table_count == 2
    assert receipt.source_custody.price_basis_status == "UNKNOWN_CONFIRMED"
    assert receipt.source_custody.external_evidence_blockers == (
        "POINT_IN_TIME_UNIVERSE",
        "AVAILABLE_AT_PROVEN",
        "OFFICIAL_PRICE_IDENTITY",
        "CORPORATE_ACTION_CONTRACT",
    )
    assert "IMMUTABLE_SOURCE_HASH" not in receipt.execution_audit.blockers
    assert receipt.maturity_score == 53
    assert receipt.research_id == "DAILY_CLOSE_OFFLINE_RL_G2_SOURCE_SNAPSHOT_V1"
    assert receipt.signal_evidence_scope == "DIAGNOSTIC_ONLY_PARTIAL_SOURCE_CUSTODY"


def test_receipt_writer_preserves_gate_and_model_scope(tmp_path: Path) -> None:
    config = ResearchRunConfig(
        database=_database(tmp_path / "daily.db"),
        codes=("000250", "000660"),
        output_directory=tmp_path / "output",
        seeds=(0,),
        calibration_epochs=10,
        execution_evidence=ExecutionEvidence.verified_for_tests(),
    )
    receipt = run_research(config)
    output = tmp_path / "receipt.json"

    write_research_receipt(receipt, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["model_scope"] == "SYNTHETIC_CALIBRATION_ONLY"
    assert payload["signal_evidence_scope"] == "DIAGNOSTIC_ONLY_PARTIAL_SOURCE_CUSTODY"
    assert payload["execution_audit"]["verdict"] == "PASS_EXECUTION_READY"
    assert payload["fresh_oos_state"] == "NOT_RUN_NO_READ"
