import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from stom_rl import daily_1520_source
from stom_rl.daily_v6_dataset import (
    DAILY_PRICE_BASIS_CAVEAT,
    build_joined_dataset,
    write_joined_dataset,
)


def _sessions(first: str, count: int) -> list[str]:
    current = date.fromisoformat(f"{first[:4]}-{first[4:6]}-{first[6:]}")
    result = []
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return result


def _make_databases(tmp_path: Path, sessions: list[str], missing: dict[str, set[str]] | None = None) -> tuple[Path, Path]:
    missing = missing or {}
    daily_path = tmp_path / "daily.db"
    five_path = tmp_path / "five.db"
    with sqlite3.connect(daily_path) as daily, sqlite3.connect(five_path) as five:
        for offset, table in enumerate(("A000001", "A000002")):
            daily.execute(
                f'''CREATE TABLE "{table}" (date TEXT, close REAL, volume REAL,
                    "상장주식수" REAL, "외국인현보유비율" REAL, "기관순매수" REAL)'''
            )
            five.execute(f'CREATE TABLE "{table}" (date INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL)')
            for index, session in enumerate(sessions):
                close = 100.0 + offset * 10 + index
                daily.execute(f'INSERT INTO "{table}" VALUES (?, ?, ?, ?, ?, ?)',
                              (f"{session[:4]}-{session[4:6]}-{session[6:]}", close, 1_000 + index,
                               1_000_000, 10 + index / 10, index - 3))
                if session not in missing.get(table, set()):
                    five.execute(f'INSERT INTO "{table}" VALUES (?, ?, ?, ?, ?, ?)',
                                 (int(session + "1520"), close, close, close, close, 100))
    return daily_path, five_path


def _rows(result, symbol="000001"):
    return [row for row in result["rows"] if row["symbol"] == symbol]


def test_features_ignore_daily_row_on_fill_date(tmp_path: Path) -> None:
    sessions = _sessions("20230102", 40)
    daily, five = _make_databases(tmp_path, sessions)
    before = build_joined_dataset(["A000001", "A000002"], daily_db_path=daily, fivemin_db_path=five)
    target = _rows(before)[25]
    with sqlite3.connect(daily) as conn:
        conn.execute('UPDATE "A000001" SET close = 999999999 WHERE date = ?',
                     (f"{sessions[25][:4]}-{sessions[25][4:6]}-{sessions[25][6:]}",))
    after = build_joined_dataset(["A000001", "A000002"], daily_db_path=daily, fivemin_db_path=five)
    poisoned = _rows(after)[25]
    for field in ("ret_1d_prev", "ret_5d_prev", "ret_20d_prev", "vol_z_20", "foreign_ratio_prev",
                  "foreign_ratio_delta_5", "inst_netbuy_norm_5"):
        assert poisoned[field] == target[field]


def test_labels_use_next_observed_exact_1520_session_and_skip_missing_bar(tmp_path: Path) -> None:
    sessions = _sessions("20230102", 40)
    daily, five = _make_databases(tmp_path, sessions, {"A000001": {sessions[11]}})
    result = build_joined_dataset(["A000001", "A000002"], daily_db_path=daily, fivemin_db_path=five, horizons=(1,))
    symbol_rows = _rows(result)
    assert sessions[11] not in {str(row["session_yyyymmdd"]) for row in symbol_rows}
    row = next(row for row in symbol_rows if row["session_yyyymmdd"] == int(sessions[10]))
    assert row["future_return_h1_1520_proxy"] == pytest.approx((112.0 / 110.0) - 1.0)
    assert row["label_reason_h1"] is None


def test_exit_gap_guard_marks_missing_exit(tmp_path: Path) -> None:
    sessions = ["20230102", "20230120"]
    daily, five = _make_databases(tmp_path, sessions)
    result = build_joined_dataset(["A000001"], daily_db_path=daily, fivemin_db_path=five, horizons=(1,))
    first = _rows(result)[0]
    assert first["future_return_h1_1520_proxy"] is None
    assert first["label_reason_h1"] == "missing_exit"


def test_split_embargo_drops_rows_with_max_horizon_exit_across_boundary(tmp_path: Path) -> None:
    sessions = ["20231229", "20240102", "20240103"]
    daily, five = _make_databases(tmp_path, sessions)
    result = build_joined_dataset(["A000001"], daily_db_path=daily, fivemin_db_path=five, horizons=(1,))
    first = _rows(result)[0]
    assert first["split"] == "embargo_dropped"
    assert result["manifest"]["split_row_counts"]["train"] == 0


def test_dataset_hash_is_deterministic_and_manifest_carries_research_locks(tmp_path: Path) -> None:
    sessions = _sessions("20230102", 40)
    daily, five = _make_databases(tmp_path, sessions)
    first = build_joined_dataset(["A000001", "A000002"], daily_db_path=daily, fivemin_db_path=five)
    second = build_joined_dataset(["A000001", "A000002"], daily_db_path=daily, fivemin_db_path=five)
    assert first["manifest"]["dataset_sha256"] == second["manifest"]["dataset_sha256"]
    assert len(first["manifest"]["false_research_locks"]) == 6
    assert not any(first["manifest"]["false_research_locks"].values())
    assert {item["daily_price_basis_caveat"] for item in first["manifest"]["features"]} == {DAILY_PRICE_BASIS_CAVEAT}

    written = write_joined_dataset(["A000001"], daily_db_path=daily, fivemin_db_path=five,
                                   out_root=tmp_path / "runs", run_id="one")
    manifest = json.loads(written["manifest_path"].read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "kronos_v6_joined_dataset.v1"
    assert manifest["dataset_sha256"]
    assert manifest["generated_utc"].endswith("Z")
    assert daily_1520_source.FALSE_RESEARCH_LOCKS == manifest["false_research_locks"]
