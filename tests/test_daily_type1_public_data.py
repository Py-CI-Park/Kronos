from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from decimal import Decimal

import pytest

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.daily_type1_public_data import (
    AMENDMENT_PATH,
    DATASET_ID,
    RECEIPT_ROLE,
    RECEIPT_SCHEMA_VERSION,
    materialize_public_data,
    verify_public_materialization,
    write_public_materialization,
)


DAILY_COLUMNS = 'date, open, high, low, close, volume, "상장주식수", "외국인주문한도수량", "외국인현보유수량", "외국인현보유비율", "기관순매수", "기관누적순매수"'
FIVE_COLUMNS = "date, open, high, low, close, volume"


def _authority(*, slots: int = 0) -> dict[str, object]:
    sessions = ["2023-12-28", "2023-12-29", "2024-01-02", "2025-06-30"]
    symbols = ["000250", *(f"{index:06d}" for index in range(1, slots + 1) if index != 250)]
    return {"stable_symbols": symbols, "sessions": {"ordered": sessions, "pairs": [[0, 1], [2, 3]], "trailing_embargo": []}, "anchor_date": "2017-12-29", "ranking": {}, "provider": {}, "query_profile": {}, "raw_sha256": "0" * 64}


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
    assert max(row["decision_date"] for row in rows) == "2025-06-30"
    assert all(row["decision_date"] <= "2025-06-30" for row in rows)
    manifest = result["manifest"]
    assert manifest["dataset_id"] == "type1-close-20260803-005"
    assert manifest["authority"]["authority_id"] == "type1-krx-authority-20260724-004"
    assert manifest["authority"]["sessions"]["train"] == {"ordered": ["2023-12-28", "2023-12-29"], "pairs": [[0, 1]], "trailing_embargo": []}
    assert manifest["authority"]["sessions"]["reused_validation"] == {"ordered": ["2024-01-02", "2025-06-30"], "pairs": [[0, 1]], "trailing_embargo": []}
    assert manifest["price_basis"] == "15:20_bar_close_proxy"
    assert manifest["sql_predicates"]["exact_1520"].endswith("% 10000 = 1520")
    assert manifest["amendment_id"] == "KRONOS-TYPE1-G002-RECOVERY-2026-07-24-004"
    amendment = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
    assert amendment["schema_version"] == "kronos.type1.g002-recovery-amendment.v4"
    assert amendment["replacement_identity"] == {
        "authority_id": "type1-krx-authority-20260724-004",
        "dataset_id": "type1-close-20260803-005",
        "train_id": "type1-public-005",
        "train_run_id": "train_type1-public-005",
        "custody_uid": "type1-fresh-oos-20260803-005",
    }
    assert amendment["authority_contract"]["authority_metadata_cutoff"] == "2026-07-24"
    assert amendment["authority_contract"]["authority_metadata_scope"] == (
        "MDCSTAT23801 instrument-master metadata only; price, calendar, ranking, "
        "public-row, and fresh-OOS access end at 2025-06-30."
    )
    assert manifest["fresh_oos"] == {"state": "NOT_RUN", "read_performed": False}


def test_canonical_bytes_three_exclusive_artifacts_and_receipt_chain(tmp_path: Path) -> None:
    daily_path, five_path = _dbs(tmp_path)
    kwargs = {"daily_db_path": daily_path, "fivemin_db_path": five_path, "authority": _authority(), "test_only": True}
    first = materialize_public_data(**kwargs)
    second = materialize_public_data(**kwargs)
    assert first["rows_bytes"] == second["rows_bytes"]
    assert first["manifest"]["output_sha256"] == hashlib.sha256(first["rows_bytes"]).hexdigest()
    written = write_public_materialization(out_root=tmp_path / "out", **kwargs)
    assert written["destination"].name == DATASET_ID
    assert {path.name for path in written["destination"].iterdir()} == {
        "public_rows.json", "dataset_manifest.json", "materializer_complete_receipt.json",
    }
    assert len({path.resolve() for path in (written["rows_path"], written["manifest_path"], written["receipt_path"])}) == 3
    receipt = json.loads(written["receipt_path"].read_text(encoding="utf-8"))
    assert receipt["schema_version"] == RECEIPT_SCHEMA_VERSION
    assert receipt["role"] == RECEIPT_ROLE
    assert receipt["status"] == "COMPLETE"
    assert receipt["dataset_manifest_sha256"] == hashlib.sha256(written["manifest_path"].read_bytes()).hexdigest()
    assert receipt["public_rows_sha256"] == hashlib.sha256(written["rows_path"].read_bytes()).hexdigest()
    assert receipt["authority_id"] == "type1-krx-authority-20260724-004"
    assert receipt["amendment_id"] == "KRONOS-TYPE1-G002-RECOVERY-2026-07-24-004"
    assert receipt["source_database_identity"] == first["manifest"]["source_database_identity"]
    assert receipt["fresh_oos"] == {"state": "NOT_RUN", "read_performed": False}
    assert receipt["execution_contract"] == {
        "proxy_time": "15:20:00", "cost_bps": 23, "fixed_notional": 60000000,
        "primary_seeds": 5, "shuffled_seeds": 5, "timesteps_per_seed": 200000,
        "outcome": "NO_GO_ONLY",
    }
    assert verify_public_materialization(written["destination"])["receipt"] == receipt
    with pytest.raises(FileExistsError):
        write_public_materialization(out_root=tmp_path / "out", **kwargs)

def test_receipt_rejects_tamper_alias_and_partial_roles(tmp_path: Path) -> None:
    daily_path, five_path = _dbs(tmp_path)
    kwargs = {"daily_db_path": daily_path, "fivemin_db_path": five_path, "authority": _authority(), "test_only": True}

    tampered = write_public_materialization(out_root=tmp_path / "tampered", **kwargs)
    receipt = json.loads(tampered["receipt_path"].read_text(encoding="utf-8"))
    receipt["public_rows_sha256"] = "0" * 64
    tampered["receipt_path"].write_bytes(canonical_json_bytes(receipt))
    with pytest.raises(ValueError, match="public_rows_sha256"):
        verify_public_materialization(tampered["destination"])

    partial = write_public_materialization(out_root=tmp_path / "partial", **kwargs)
    receipt = json.loads(partial["receipt_path"].read_text(encoding="utf-8"))
    del receipt["artifact_roles"]["public_rows.json"]
    partial["receipt_path"].write_bytes(canonical_json_bytes(receipt))
    with pytest.raises(ValueError, match="artifact roles"):
        verify_public_materialization(partial["destination"])

    aliased = write_public_materialization(out_root=tmp_path / "aliased", **kwargs)
    aliased["receipt_path"].unlink()
    os.link(aliased["rows_path"], aliased["receipt_path"])
    with pytest.raises(ValueError, match="physically distinct"):
        verify_public_materialization(aliased["destination"])


def test_500_slot_cartesian_counts_and_public_cutoff(tmp_path: Path) -> None:
    daily_path, five_path = _dbs(tmp_path)
    result = materialize_public_data(
        daily_db_path=daily_path,
        fivemin_db_path=five_path,
        authority=_authority(slots=500),
        test_only=True,
    )
    manifest = result["manifest"]
    assert manifest["row_count"] == 2000
    assert manifest["split_row_counts"] == {"train": 1000, "reused_validation": 1000}
    assert manifest["split_symbol_counts"] == {"train": 500, "reused_validation": 500}
    assert manifest["expected"]["split_rows"] == {"train": 1000, "reused_validation": 1000}
    assert manifest["expected"]["split_pairs"] == {"train": 1, "reused_validation": 1}
    assert manifest["expected"]["split_embargo"] == {"train": 0, "reused_validation": 0}
    assert max(row["decision_date"] for row in result["rows"]) == "2025-06-30"

def test_production_rejects_injected_authority(tmp_path: Path) -> None:
    daily_path, five_path = _dbs(tmp_path)
    with pytest.raises(ValueError, match="test_only"):
        materialize_public_data(daily_db_path=daily_path, fivemin_db_path=five_path, authority=_authority())
