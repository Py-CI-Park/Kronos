from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from stom_rl.daily_market_local_db_audit import (
    LocalDbCustodyPaths,
    audit_local_databases,
    main,
    write_local_db_custody,
)
from stom_rl.daily_market_rl_contract import DailyMarketRlContractError


def _paths(tmp_path: Path, *, duplicate: bool = False) -> LocalDbCustodyPaths:
    database = tmp_path / "daily.db"
    stockinfo = tmp_path / "stockinfo.db"
    with sqlite3.connect(database) as connection:
        _ = connection.execute(
            'CREATE TABLE "A000001" (date INTEGER, open INTEGER, high INTEGER, low INTEGER, close INTEGER, volume INTEGER)'
        )
        _ = connection.execute(
            'INSERT INTO "A000001" VALUES (20260102, 10, 11, 9, 10, 100)'
        )
        _ = connection.execute(
            'INSERT INTO "A000001" VALUES (?, 11, 12, 10, 11, 120)',
            (20260102 if duplicate else 20260103,),
        )
    with sqlite3.connect(stockinfo) as connection:
        _ = connection.execute(
            'CREATE TABLE stockinfo ("index" TEXT, "종목명" TEXT, "코스닥" INTEGER)'
        )
        _ = connection.execute('INSERT INTO stockinfo VALUES ("000001", "테스트", 0)')
    return LocalDbCustodyPaths(
        repository_root=tmp_path,
        daily_database=database,
        stockinfo_database=stockinfo,
        output_directory=tmp_path / "output",
    )


def test_local_db_audit_preserves_research_use_and_blocks_authority_claims(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)

    receipt = audit_local_databases(paths)

    assert receipt.quality.table_count == 1
    assert receipt.quality.total_row_count == 2
    assert receipt.quality.first_date == "20260102"
    assert receipt.quality.last_date == "20260103"
    assert receipt.quality.quality_passed is True
    assert receipt.local_research_allowed is True
    assert receipt.price_basis == "UNKNOWN_LOCAL_DB_BASIS"
    assert receipt.universe_basis == "CURRENT_SNAPSHOT_NOT_PIT"
    assert receipt.blockers == (
        "D0_PRICE_BASIS_UNKNOWN_LOCAL_DB",
        "D1_CURRENT_SNAPSHOT_NOT_PIT",
    )
    assert receipt.independent_oos_claim_allowed is False
    assert receipt.fresh_holdout_read is False

    output = write_local_db_custody(receipt, paths.output_directory)
    assert output.is_file()
    with pytest.raises(DailyMarketRlContractError, match="LOCAL_DB_OUTPUT_UNTRUSTED"):
        _ = write_local_db_custody(receipt, paths.output_directory)


def test_local_db_audit_blocks_duplicate_date_quality(tmp_path: Path) -> None:
    receipt = audit_local_databases(_paths(tmp_path, duplicate=True))

    assert receipt.quality.duplicate_date_table_count == 1
    assert receipt.quality.quality_passed is False
    assert receipt.local_research_allowed is False
    assert "LOCAL_DB_SCHEMA_OR_DUPLICATE_QUALITY_FAILED" in receipt.blockers


def test_registered_local_db_paths_require_explicit_canonical_root(
    tmp_path: Path,
) -> None:
    paths = LocalDbCustodyPaths.registered(tmp_path)

    assert (
        paths.daily_database == tmp_path / "_database" / "Stock_Database_ohlcv_1day.db"
    )
    assert paths.output_directory.name == "DAILY_MARKET_LOCAL_DB_CUSTODY_2026_08_14_001"
    assert replace(paths, repository_root=tmp_path).repository_root == tmp_path


def test_local_db_audit_cli_requires_explicit_root() -> None:
    with pytest.raises(
        DailyMarketRlContractError,
        match="LOCAL_DB_RUNNER_REQUIRES_REPOSITORY_ROOT",
    ):
        _ = main(())
