import sqlite3
from pathlib import Path

from stom_rl.etf_research.data import DataCustodyEvidence, audit_data_readiness, load_price_series


def _write_price_table(path: Path, code: str, rows: list[tuple[int, float, float, float, float, float]]) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            f'CREATE TABLE "A{code}" (date INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL)'
        )
        connection.executemany(f'INSERT INTO "A{code}" VALUES (?, ?, ?, ?, ?, ?)', rows)


def test_data_audit_blocks_when_point_in_time_custody_is_missing(tmp_path: Path) -> None:
    # Given: valid OHLCV exists but official historical metadata does not.
    database = tmp_path / "daily.db"
    _write_price_table(
        database,
        "069500",
        [
            (20260102, 100.0, 103.0, 99.0, 102.0, 1000.0),
            (20260105, 102.0, 104.0, 101.0, 103.0, 1100.0),
        ],
    )
    series = load_price_series(database, ("069500",))

    # When: the research readiness gate is evaluated fail-closed.
    receipt = audit_data_readiness(series, DataCustodyEvidence.unverified())

    # Then: structural gates pass but Q1 remains blocked by missing custody.
    assert receipt.verdict == "BLOCKED_DATA_CUSTODY"
    assert receipt.gates["READ_ONLY_SOURCE"] is True
    assert receipt.gates["STRICT_DATE_ORDER"] is True
    assert receipt.gates["VALID_OHLC"] is True
    assert receipt.gates["POINT_IN_TIME_UNIVERSE"] is False
    assert receipt.q3_ppo_allowed is False


def test_data_audit_rejects_duplicate_dates_and_invalid_ohlc(tmp_path: Path) -> None:
    # Given: a source table contains a duplicate date and an impossible high/low range.
    database = tmp_path / "daily.db"
    _write_price_table(
        database,
        "102110",
        [
            (20260102, 100.0, 99.0, 98.0, 101.0, 1000.0),
            (20260102, 101.0, 102.0, 100.0, 101.0, 1000.0),
        ],
    )
    series = load_price_series(database, ("102110",))

    # When: structural integrity is audited with otherwise complete metadata.
    receipt = audit_data_readiness(series, DataCustodyEvidence.verified_for_tests())

    # Then: both integrity gates fail and promotion remains locked.
    assert receipt.gates["STRICT_DATE_ORDER"] is False
    assert receipt.gates["VALID_OHLC"] is False
    assert receipt.verdict == "BLOCKED_DATA_INTEGRITY"
    assert receipt.q3_ppo_allowed is False


def test_price_loader_preserves_leading_zero_codes(tmp_path: Path) -> None:
    # Given: a six-digit code starts with zero.
    database = tmp_path / "daily.db"
    _write_price_table(database, "069500", [(20260102, 100.0, 101.0, 99.0, 100.0, 10.0)])

    # When: the read-only SQLite adapter loads the table.
    series = load_price_series(database, ("069500",))

    # Then: the code remains a string with its leading zero.
    assert series[0].code == "069500"

