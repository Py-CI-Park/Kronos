from __future__ import annotations

import hashlib
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl.daily_1520_source import (  # noqa: E402
    CAUSAL_CUTOFF_KST,
    EXPECTED_COLUMNS,
    OFFICIAL_CLOSE,
    PRICE_BASIS,
    SCHEMA_VERSION,
    build_source_artifact,
    build_source_coverage,
    connect_readonly,
    read_exact_1520_rows,
    resolve_5min_table,
)


def _create_table(conn: sqlite3.Connection, table: str, *, date_type: str = "INTEGER") -> None:
    conn.execute(
        f'CREATE TABLE "{table}" '
        f'("date" {date_type}, "open" REAL, "high" REAL, "low" REAL, "close" REAL, "volume" INTEGER)'
    )


def _insert_bar(
    conn: sqlite3.Connection,
    table: str,
    timestamp: int | str,
    *,
    close: float,
    volume: int,
) -> None:
    conn.execute(
        f'INSERT INTO "{table}" (date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?)',
        (timestamp, close - 1.0, close + 2.0, close - 2.0, close, volume),
    )


def _create_5min_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    _create_table(conn, "A000250")
    _create_table(conn, "A035720")
    _insert_bar(conn, "A000250", 202401021515, close=99.0, volume=10)
    _insert_bar(conn, "A000250", 202401021520, close=100.0, volume=200)
    _insert_bar(conn, "A000250", 202401021525, close=101.0, volume=999999)
    _insert_bar(conn, "A000250", 202401031525, close=300.0, volume=999999)
    _insert_bar(conn, "A000250", 202401041520, close=104.0, volume=240)
    for timestamp, close in ((202401021520, 720.0), (202401031520, 721.0), (202401041520, 722.0)):
        _insert_bar(conn, "A035720", timestamp, close=close, volume=720)
    conn.commit()
    conn.close()
    return path


def test_constants_freeze_1520_proxy_not_official_close():
    assert SCHEMA_VERSION == "kronos_daily_1520_source.v1"
    assert CAUSAL_CUTOFF_KST == "15:20:00"
    assert PRICE_BASIS == "15:20_bar_close_proxy"
    assert OFFICIAL_CLOSE is False
    assert EXPECTED_COLUMNS == ("date", "open", "high", "low", "close", "volume")


def test_resolve_5min_table_accepts_only_numeric_a_prefixed_tables_and_preserves_leading_zero():
    resolved = resolve_5min_table("000250")
    assert resolved.table == "A000250"
    assert resolved.symbol == "000250"
    assert resolve_5min_table("A035720").symbol == "035720"
    for bad in ("Q500001", "00025", "00AB12", "A00AB12", "AA000250", "../A000250", "A000250;DROP"):
        with pytest.raises(ValueError, match="six numeric digits"):
            resolve_5min_table(bad)


def test_connect_readonly_enables_query_only_and_blocks_writes(tmp_path: Path):
    db_path = _create_5min_db(tmp_path / "five_min.db")
    with connect_readonly(db_path) as conn:
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM "A000250"').fetchone()[0] == 5
        with pytest.raises(sqlite3.OperationalError):
            conn.execute('INSERT INTO "A000250" (date, open, high, low, close, volume) VALUES (209901011520, 1, 1, 1, 1, 1)')


def test_read_exact_1520_rows_filters_exact_time_without_nearest_or_daily_fallback(tmp_path: Path):
    db_path = _create_5min_db(tmp_path / "five_min.db")
    rows = read_exact_1520_rows(db_path, "000250", start_date="2024-01-02", end_date="2024-01-04")

    assert [row.session_date for row in rows] == ["2024-01-02", "2024-01-04"]
    assert [row.timestamp_yyyymmddhhmm for row in rows] == [202401021520, 202401041520]
    assert all(row.timestamp_yyyymmddhhmm % 10000 == 1520 for row in rows)
    assert all(row.timestamp_kst.endswith("T15:20:00+09:00") for row in rows)
    assert rows[0].symbol == "000250"
    assert rows[0].table == "A000250"
    assert rows[0].price_1520_close_proxy == 100.0
    assert rows[0].bar_volume_1520 == 200
    assert rows[0].close == 100.0
    assert rows[0].official_close is False
    assert rows[0].price_basis == PRICE_BASIS
    assert rows[0].causal_cutoff_kst == CAUSAL_CUTOFF_KST
    assert rows[0].tradable is True
    assert rows[0].exclusion_reason is None
    assert {row.session_date for row in rows} == {"2024-01-02", "2024-01-04"}
    assert rows[0].source_table == "A000250"
    assert rows[0].source_columns == EXPECTED_COLUMNS


def test_bar_volume_is_not_cumulative_and_amount_is_not_price_volume_approximation(tmp_path: Path):
    db_path = _create_5min_db(tmp_path / "five_min.db")
    row = read_exact_1520_rows(db_path, "A000250", start_date=20240102, end_date=20240102)[0]

    assert row.bar_volume_1520 == 200
    assert row.bar_volume_status == "SINGLE_5MIN_BAR_VOLUME_AT_15_20_ONLY"
    assert row.volume_to_1520 is None
    assert row.cumulative_volume_to_1520 is None
    assert "SINGLE_5MIN_BAR_VOLUME" in row.volume_to_1520_status
    assert row.amount_to_1520 is None
    assert "DO_NOT_APPROXIMATE_PRICE_X_VOLUME" in row.amount_to_1520_status
    assert row.close * row.bar_volume_1520 == 20000.0
    assert row.amount_to_1520 != row.close * row.bar_volume_1520


def test_build_source_coverage_reports_missing_bars_false_locks_and_file_content_hash(tmp_path: Path):
    db_path = _create_5min_db(tmp_path / "five_min.db")
    expected_sha = hashlib.sha256(db_path.read_bytes()).hexdigest()

    coverage = build_source_coverage(db_path, ["000250", "035720"])
    by_table = {entry["table"]: entry for entry in coverage["tables"]}

    assert coverage["schema_version"] == SCHEMA_VERSION
    assert coverage["source_snapshot"]["sha256"] == expected_sha
    assert coverage["source_db_sha256"] == expected_sha
    assert coverage["source_snapshot"]["byte_length"] == db_path.stat().st_size
    assert coverage["source_snapshot"]["hash_basis"] == "ACTUAL_FILE_BYTES_STREAMING_SHA256"
    assert coverage["first_valid_date"] == "2024-01-02"
    assert coverage["last_valid_date"] == "2024-01-04"
    assert coverage["exact_1520_row_count"] == 5
    assert coverage["missing_1520_date_count"] == 1
    assert coverage["missing_rows_synthesized"] is False
    assert set(coverage["false_research_locks"]) == {
        "promotion_allowed",
        "model_build_allowed",
        "paper_forward_allowed",
        "live_broker_order_allowed",
        "profitability_claim_allowed",
        "go_summary_allowed",
    }
    assert all(value is False for value in coverage["false_research_locks"].values())
    assert coverage["no_claim_flags"]["official_close_claim"] is False
    assert coverage["no_claim_flags"]["nearest_bar_fallback_claim"] is False

    assert by_table["A000250"]["first_valid_date"] == "2024-01-02"
    assert by_table["A000250"]["last_valid_date"] == "2024-01-04"
    assert by_table["A000250"]["exact_1520_row_count"] == 2
    assert by_table["A000250"]["missing_1520_date_count"] == 1
    assert by_table["A000250"]["missing_dates"] == ["2024-01-03"]
    assert by_table["A000250"]["missing_exclusion_reason"] == "MISSING_1520_BAR"
    assert by_table["A000250"]["missing_rows_synthesized"] is False
    assert by_table["A035720"]["exact_1520_row_count"] == 3
    assert by_table["A035720"]["missing_1520_date_count"] == 0


def test_build_source_artifact_ranged_coverage_matches_filtered_rows(tmp_path: Path):
    db_path = _create_5min_db(tmp_path / "five_min.db")

    artifact = build_source_artifact(db_path, "000250", start_date="2024-01-02", end_date="2024-01-02")
    by_table = {entry["table"]: entry for entry in artifact["tables"]}

    assert [row["session_date"] for row in artifact["rows"]] == ["2024-01-02"]
    assert artifact["source_calendar"] == ["2024-01-02"]
    assert artifact["first_valid_date"] == "2024-01-02"
    assert artifact["last_valid_date"] == "2024-01-02"
    assert artifact["exact_1520_row_count"] == 1
    assert artifact["missing_1520_date_count"] == 0
    assert by_table["A000250"]["first_valid_date"] == "2024-01-02"
    assert by_table["A000250"]["last_valid_date"] == "2024-01-02"
    assert by_table["A000250"]["exact_1520_row_count"] == 1
    assert by_table["A000250"]["missing_dates"] == []
    assert all(row["session_date"] == "2024-01-02" for row in artifact["rows"])

def test_rejects_non_exact_schema(tmp_path: Path):
    db_path = tmp_path / "bad_schema.db"
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE "A000250" ("date" INTEGER, "open" REAL, "high" REAL, "low" REAL, "close" REAL, "volume" INTEGER, "amount" REAL)')
    conn.commit()
    conn.close()

    with pytest.raises(ValueError, match="schema must be exactly"):
        read_exact_1520_rows(db_path, "000250")


def test_rejects_text_timestamp_even_when_digits_match_1520(tmp_path: Path):
    db_path = tmp_path / "bad_timestamp.db"
    conn = sqlite3.connect(db_path)
    _create_table(conn, "A000250", date_type="TEXT")
    _insert_bar(conn, "A000250", "202401021520", close=100.0, volume=200)
    conn.commit()
    conn.close()

    with pytest.raises(ValueError, match="integer YYYYMMDDHHMM"):
        read_exact_1520_rows(db_path, "000250")


def test_missing_1520_bar_never_falls_back_to_later_timestamp(tmp_path: Path):
    db_path = tmp_path / "missing_only.db"
    conn = sqlite3.connect(db_path)
    _create_table(conn, "A000250")
    _insert_bar(conn, "A000250", 202401021525, close=125.0, volume=999)
    conn.commit()
    conn.close()

    assert read_exact_1520_rows(db_path, "000250", start_date="2024-01-02", end_date="2024-01-02") == []
    coverage = build_source_coverage(db_path, ["000250"], start_date="2024-01-02", end_date="2024-01-02")
    table = coverage["tables"][0]

    assert coverage["source_calendar"] == ["2024-01-02"]
    assert coverage["exact_1520_row_count"] == 0
    assert coverage["missing_1520_date_count"] == 1
    assert table["first_valid_date"] == "2024-01-02"
    assert table["last_valid_date"] == "2024-01-02"
    assert table["exact_1520_row_count"] == 0
    assert table["valid_session_count"] == 1
    assert table["expected_session_count"] == 1
    assert table["missing_1520_date_count"] == 1
    assert table["missing_dates"] == ["2024-01-02"]
    assert table["missing_exclusion_reason"] == "MISSING_1520_BAR"
    assert table["missing_rows_synthesized"] is False
    assert table["tradable_when_missing"] is False


def test_build_source_coverage_uses_each_table_observed_calendar_without_cross_symbol_missing(tmp_path: Path):
    db_path = tmp_path / "nonoverlap.db"
    conn = sqlite3.connect(db_path)
    _create_table(conn, "A000250")
    _create_table(conn, "A035720")
    _insert_bar(conn, "A000250", 202401021520, close=100.0, volume=100)
    _insert_bar(conn, "A000250", 202401041520, close=104.0, volume=104)
    _insert_bar(conn, "A035720", 202401031520, close=721.0, volume=721)
    conn.commit()
    conn.close()

    coverage = build_source_coverage(db_path, ["000250", "035720"], start_date="2024-01-02", end_date="2024-01-04")
    by_table = {entry["table"]: entry for entry in coverage["tables"]}

    assert coverage["source_calendar"] == ["2024-01-02", "2024-01-03", "2024-01-04"]
    assert coverage["missing_1520_date_count"] == 0
    assert by_table["A000250"]["expected_session_count"] == 2
    assert by_table["A000250"]["missing_1520_date_count"] == 0
    assert by_table["A000250"]["missing_dates"] == []
    assert by_table["A035720"]["first_valid_date"] == "2024-01-03"
    assert by_table["A035720"]["last_valid_date"] == "2024-01-03"
    assert by_table["A035720"]["expected_session_count"] == 1
    assert by_table["A035720"]["missing_1520_date_count"] == 0
    assert by_table["A035720"]["missing_dates"] == []
