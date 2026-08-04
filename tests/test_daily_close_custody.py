from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

import stom_rl.daily_close_research.custody as custody_module
from stom_rl.daily_close_research.contracts import ExecutionEvidence
from stom_rl.daily_close_research.custody import bind_source_hash, inspect_source_custody


def _database(path: Path) -> Path:
    with sqlite3.connect(path) as connection:
        connection.execute(
            'CREATE TABLE "A000250" (date INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL)'
        )
        connection.executemany(
            'INSERT INTO "A000250" VALUES (?, ?, ?, ?, ?, ?)',
            ((20260102, 100.0, 102.0, 99.0, 101.0, 10_000.0), (20260103, 101.0, 103.0, 100.0, 102.0, 11_000.0)),
        )
    return path


def test_source_inspection_is_read_only_and_binds_exact_bytes(tmp_path: Path) -> None:
    # Given
    database = _database(tmp_path / "daily.db")
    before = hashlib.sha256(database.read_bytes()).hexdigest()

    # When
    receipt = inspect_source_custody(database, ("000250",))

    # Then
    assert receipt.database_sha256 == before
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    assert receipt.read_only is True
    assert receipt.query_only is True
    assert receipt.tables[0].core_columns_present is True
    assert receipt.tables[0].first_date == 20260102
    assert receipt.tables[0].last_date == 20260103


def test_local_hash_does_not_promote_external_authority_gates(tmp_path: Path) -> None:
    # Given
    receipt = inspect_source_custody(_database(tmp_path / "daily.db"), ("000250", "000660"))

    # When
    evidence = bind_source_hash(ExecutionEvidence.unverified(), receipt)

    # Then
    assert receipt.requested_table_count == 2
    assert receipt.available_table_count == 1
    assert evidence.immutable_source_hash is True
    assert evidence.point_in_time_universe is False
    assert evidence.available_at_proven is False
    assert evidence.official_price_identity is False
    assert evidence.corporate_action_contract is False


def test_source_change_after_snapshot_is_rejected(tmp_path: Path) -> None:
    # Given
    database = _database(tmp_path / "daily.db")
    receipt = inspect_source_custody(database, ("000250",))
    with database.open("ab") as target:
        target.write(b"changed-after-snapshot")

    # When / Then
    with pytest.raises(custody_module.SourceChangedDuringRunError, match="changed during research run"):
        custody_module.assert_source_unchanged(receipt)
