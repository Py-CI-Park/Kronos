from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from decimal import Decimal

import pytest

from stom_rl.daily_type1_public_data import DATASET_ID, materialize_public_data, write_public_materialization


DAILY_COLUMNS = 'date, open, high, low, close, volume, "상장주식수", "외국인주문한도수량", "외국인현보유수량", "외국인현보유비율", "기관순매수", "기관누적순매수"'
FIVE_COLUMNS = "date, open, high, low, close, volume"


def _authority() -> dict[str, object]:
    sessions = ["2023-12-28", "2023-12-29", "2024-01-02", "2025-06-30"]
    return {"stable_symbols": ["000250"], "sessions": {"ordered": sessions, "pairs": [[0, 1], [2, 3]], "trailing_embargo": []}, "anchor_date": "2017-12-29", "ranking": {}, "provider": {}, "query_profile": {}, "raw_sha256": "0" * 64}


def _dbs(tmp_path: Path) -> tuple[Path, Path]:
    daily_path, five_path = tmp_path / "daily.sqlite", tmp_path / "five.sqlite"
    with sqlite3.connect(daily_path) as conn:
        conn.execute(f'CREATE TABLE "A000250" ({DAILY_COLUMNS})')
        for day in range(1, 26):
            conn.execute('INSERT INTO "A000250" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (20171200 + day, day, day, day, day, day * 10, 100, 0, 0, day, day, 0))
        conn.executemany('INSERT INTO "A000250" VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', [
            (20231228, 100, 100, 100, 100, 10, 100, 0, 0, 1, 1, 0),
            (20231229, 101, 101, 101, 101, 11, 100, 0, 0, 2, 2, 0),
            (20240102, 102, 102, 102, 102, 12, 100, 0, 0, 3, 3, 0),
            (20250630, 103, 103, 103, 103, 13, 100, 0, 0, 4, 4, 0),
            (20250701, 999999, 999999, 999999, 999999, 999999, 999999, 0, 0, 999999, 999999, 0),
        ])
    with sqlite3.connect(five_path) as conn:
        conn.execute(f'CREATE TABLE "A000250" ({FIVE_COLUMNS})')
        conn.executemany('INSERT INTO "A000250" VALUES (?, ?, ?, ?, ?, ?)', [
            (202312281520, 1, 1, 1, 90, 1), (202312291520, 1, 1, 1, 100, 1), (202312291515, 1, 1, 1, 999, 1),
            (202401021520, 1, 1, 1, 110, 1), (202506301520, 1, 1, 1, 120, 1),
            (202507011520, 1, 1, 1, 999999, 1),
        ])
    return daily_path, five_path


def _result(tmp_path: Path) -> dict[str, object]:
    daily_path, five_path = _dbs(tmp_path)
    return materialize_public_data(daily_db_path=daily_path, fivemin_db_path=five_path, authority=_authority(), test_only=True)


def test_authority_sessions_exact_proxy_leading_zero_and_split_local_pairs(tmp_path: Path) -> None:
    result = _result(tmp_path)
    rows = result["rows"]
    assert isinstance(rows, list)
    assert [row["symbol"] for row in rows] == ["000250", "000250", "000250", "000250"]
    assert [row["decision_date"] for row in rows] == ["2023-12-28", "2023-12-29", "2024-01-02", "2025-06-30"]
    assert [row["split"] for row in rows] == ["train", "train", "reused_validation", "reused_validation"]
    assert rows[0]["gross_return"] == str(Decimal(100) / Decimal(90) - Decimal(1))
    assert rows[1]["gross_return"] is None
    assert rows[2]["gross_return"] == str(Decimal(120) / Decimal(110) - Decimal(1))
    assert rows[3]["gross_return"] is None
    manifest = result["manifest"]
    assert manifest["authority"]["sessions"]["train"] == {"ordered": ["2023-12-28", "2023-12-29"], "pairs": [[0, 1]], "trailing_embargo": []}
    assert manifest["authority"]["sessions"]["reused_validation"] == {"ordered": ["2024-01-02", "2025-06-30"], "pairs": [[0, 1]], "trailing_embargo": []}
    assert manifest["fresh_oos"] == {"state": "NOT_RUN", "read_performed": False}


def test_canonical_bytes_and_exclusive_replacement_identity_create(tmp_path: Path) -> None:
    daily_path, five_path = _dbs(tmp_path)
    kwargs = {"daily_db_path": daily_path, "fivemin_db_path": five_path, "authority": _authority(), "test_only": True}
    first = materialize_public_data(**kwargs)
    second = materialize_public_data(**kwargs)
    assert first["rows_bytes"] == second["rows_bytes"]
    assert first["manifest"]["output_sha256"] == hashlib.sha256(first["rows_bytes"]).hexdigest()
    written = write_public_materialization(out_root=tmp_path / "out", **kwargs)
    assert written["destination"].name == DATASET_ID
    assert json.loads(written["rows_path"].read_text(encoding="utf-8")) == first["rows"]
    with pytest.raises(FileExistsError):
        write_public_materialization(out_root=tmp_path / "out", **kwargs)


def test_production_rejects_injected_authority(tmp_path: Path) -> None:
    daily_path, five_path = _dbs(tmp_path)
    with pytest.raises(ValueError, match="test_only"):
        materialize_public_data(daily_db_path=daily_path, fivemin_db_path=five_path, authority=_authority())
