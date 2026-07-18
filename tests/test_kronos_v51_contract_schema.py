from __future__ import annotations

import copy
import json

import sqlite3
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl.daily_1520_source import build_source_artifact, read_exact_1520_rows  # noqa: E402
from stom_rl.daily_v51_causal_panel import build_causal_panel, validate_causal_panel  # noqa: E402

SCHEMAS = REPO_ROOT / "docs" / "schemas"

def _load_validator(name: str) -> tuple[dict[str, object], Draft202012Validator]:
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema, Draft202012Validator(schema)


def _create_5min_fixture(path: Path) -> Path:
    sessions = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08", "2024-01-09"]
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE "A000250" ("date" INTEGER, "open" REAL, "high" REAL, "low" REAL, "close" REAL, "volume" INTEGER)')
    for index, session in enumerate(sessions):
        compact = int(session.replace("-", "") + "1520")
        close = 100.0 + (index * 5.0)
        conn.execute(
            'INSERT INTO "A000250" (date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?)',
            (compact, close - 1.0, close + 2.0, close - 2.0, close, 1000 + index),
        )
    conn.commit()
    conn.close()
    return path


def _assert_schema_rejects(validator: Draft202012Validator, artifact: dict[str, object], path: tuple[object, ...], value: object) -> None:
    mutated = copy.deepcopy(artifact)
    target: object = mutated
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]
    with pytest.raises(ValidationError):
        validator.validate(mutated)


def _assert_schema_rejects_without_key(validator: Draft202012Validator, artifact: dict[str, object], path: tuple[object, ...]) -> None:
    mutated = copy.deepcopy(artifact)
    target: object = mutated
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    del target[path[-1]]  # type: ignore[index]
    with pytest.raises(ValidationError):
        validator.validate(mutated)


def test_v51_source_artifact_and_causal_panel_validate_executable_schemas(tmp_path: Path) -> None:
    db_path = _create_5min_fixture(tmp_path / "_database" / "Stock_Database_ohlcv_5min.db")
    source_schema, source_validator = _load_validator("kronos_daily_1520_source.v1.schema.json")
    _causal_schema, causal_validator = _load_validator("kronos_daily_v51_causal_panel.v1.schema.json")

    source_artifact = build_source_artifact(db_path, "000250")
    source_validator.validate(source_artifact)
    json.dumps(source_artifact, sort_keys=True, allow_nan=False)

    internal_row = read_exact_1520_rows(db_path, "000250")[0]
    assert internal_row.timestamp_yyyymmddhhmm == 202401021520
    exact_row = internal_row.as_dict()
    required_source_fields = set(source_schema["$defs"]["sourceRow"]["required"])
    assert required_source_fields == set(exact_row)
    assert required_source_fields == set(source_artifact["rows"][0])
    assert len(source_artifact["rows"]) == source_artifact["exact_1520_row_count"] == 6
    assert source_artifact["rows"][0]["symbol"] == "000250"
    assert source_artifact["rows"][0]["price_1520_close_proxy"] == source_artifact["rows"][0]["close"]
    assert source_artifact["rows"][0]["volume_to_1520"] is None
    assert source_artifact["rows"][0]["amount_to_1520"] is None
    assert source_artifact["rows"][0]["official_close"] is False
    assert source_artifact["source_db_path"].replace("\\", "/").endswith("_database/Stock_Database_ohlcv_5min.db")
    assert source_artifact["rows"][0]["timestamp_yyyymmddhhmm"] == "202401021520"
    assert source_artifact["rows"][0]["volume_to_1520_status"] == "NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY"
    assert source_artifact["rows"][0]["cumulative_volume_to_1520"] is None
    assert source_artifact["rows"][0]["cumulative_volume_to_1520_status"] == "NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY"
    assert source_artifact["rows"][0]["amount_to_1520_status"] == "NOT_AVAILABLE_5MIN_DB_HAS_NO_AMOUNT_COLUMN_DO_NOT_APPROXIMATE_PRICE_X_VOLUME"

    bad_source = copy.deepcopy(source_artifact)
    bad_source["rows"][0]["unexpected"] = True
    with pytest.raises(ValidationError):
        source_validator.validate(bad_source)
    _assert_schema_rejects(source_validator, source_artifact, ("source_db_path",), str(tmp_path / "five_min.db"))
    _assert_schema_rejects(source_validator, source_artifact, ("rows", 0, "symbol"), "00AB12")
    _assert_schema_rejects(source_validator, source_artifact, ("rows", 0, "table"), "A00AB12")
    _assert_schema_rejects(source_validator, source_artifact, ("rows", 0, "timestamp_yyyymmddhhmm"), "202401021530")
    _assert_schema_rejects(source_validator, source_artifact, ("rows", 0, "timestamp_yyyymmddhhmm"), 202401021520)
    _assert_schema_rejects(source_validator, source_artifact, ("false_research_locks", "promotion_allowed"), True)
    _assert_schema_rejects(source_validator, source_artifact, ("six_locks_false", "unexpected"), False)

    observation = {
        "symbol": "000250",
        "session": "2024-01-02",
        "timestamp": "2024-01-02T15:19:00+09:00",
        "feature_score": 1.0,
        "source_db_path": source_artifact["source_db_path"],
    }
    panel = build_causal_panel(
        [observation],
        source_artifact["rows"],
        source_calendar=source_artifact["source_calendar"],
        source_identity={
            "schema_version": source_artifact["schema_version"],
            "source_db_path": source_artifact["source_db_path"],
            "source_db_sha256": source_artifact["source_db_sha256"],
        },
    )
    validate_causal_panel(panel)
    causal_validator.validate(panel)
    json.dumps(panel, sort_keys=True, allow_nan=False)

    row = panel["rows"][0]
    assert panel["horizon_days"] == [1, 3, 5]
    assert panel["source_identity"]["identity_basis"] == "explicit"
    assert panel["source_identity"]["source_db_path"] == source_artifact["source_db_path"]
    assert panel["source_identity"]["source_db_sha256"] == source_artifact["source_db_sha256"]
    assert panel["source_identity"]["schema_versions"] == ["kronos_daily_1520_source.v1"]
    assert panel["source_identity"]["source_columns"] == ["date", "open", "high", "low", "close", "volume"]
    assert panel["source_identity"]["source_tables"] == ["A000250"]
    assert panel["audit"]["source_identity_present"] is True
    assert panel["audit"]["source_audit"]["approved_source_db_paths"] == [source_artifact["source_db_path"]]
    assert panel["audit"]["source_audit"]["approved_source_tables"] == ["A000250"]
    assert panel["audit"]["exact_1520_source"]["source_columns"] == ["close", "date", "high", "low", "open", "volume"]
    assert panel["audit"]["source_audit"]["approved_source_columns"] == ["close", "date", "high", "low", "open", "volume"]
    assert panel["label_columns"] == [
        "future_return_h1_1520_proxy",
        "future_return_h3_1520_proxy",
        "future_return_h5_1520_proxy",
    ]
    assert row["label_statuses"]["future_return_h1_1520_proxy"]["status"] == "available"
    assert row["label_statuses"]["future_return_h3_1520_proxy"]["status"] == "available"
    assert row["label_statuses"]["future_return_h5_1520_proxy"]["status"] == "available"
    assert row["entry_1520"]["bar_volume_status"] == "SINGLE_5MIN_BAR_VOLUME_AT_15_20_ONLY"
    assert row["entry_1520"]["timestamp_yyyymmddhhmm"] == "202401021520"
    assert row["entry_1520"]["amount_to_1520"] is None
    assert row["entry_1520"]["official_close"] is False
    assert "entry" not in row
    assert "exit_1520" not in row
    assert "entry_1520" in row
    assert "exit_1520_by_label" in row
    assert row["entry_1520"]["cumulative_volume_to_1520"] is None
    assert row["entry_1520"]["amount_to_1520_status"] == "NOT_AVAILABLE_5MIN_DB_HAS_NO_AMOUNT_COLUMN_DO_NOT_APPROXIMATE_PRICE_X_VOLUME"

    bad_panel = copy.deepcopy(panel)
    bad_panel["rows"][0]["max_observation_timestamp"] = "2024-01-02T15:20:01+09:00"
    with pytest.raises(ValidationError):
        causal_validator.validate(bad_panel)
    _assert_schema_rejects(causal_validator, panel, ("unexpected_top_level",), True)
    _assert_schema_rejects(causal_validator, panel, ("fallback_policy",), "nearest_fallback_allowed")
    _assert_schema_rejects(causal_validator, panel, ("amount_policy",), "price_times_volume_allowed")
    _assert_schema_rejects(causal_validator, panel, ("forbidden_daily_fields",), ["future_return_1d"])
    _assert_schema_rejects(causal_validator, panel, ("forbidden_observation_source_suffix",), "_database/Stock_Database_ohlcv_5min.db")
    _assert_schema_rejects(causal_validator, panel, ("cutoff",), "15:19:00")
    _assert_schema_rejects(causal_validator, panel, ("audit", "observation_field_policy", "legacy_future_return_1d_allowed"), True)
    _assert_schema_rejects(causal_validator, panel, ("audit", "observation_field_policy", "unexpected"), False)
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "cutoff"), "15:19:00")
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "cutoff_timestamp"), "2024-01-02T15:19:00+09:00")
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "unexpected"), True)
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "label_statuses", "future_return_h1_1520_proxy", "status"), "ok")
    _assert_schema_rejects(causal_validator, panel, ("locks", "profit_claim"), True)
    _assert_schema_rejects(causal_validator, panel, ("promotion_claims", "profit"), True)
    _assert_schema_rejects(causal_validator, panel, ("locks", "extra_lock"), False)
    _assert_schema_rejects(causal_validator, panel, ("promotion_claims", "extra_claim"), False)
    _assert_schema_rejects(causal_validator, panel, ("source_identity",), None)
    _assert_schema_rejects(causal_validator, panel, ("source_identity", "unexpected"), True)
    _assert_schema_rejects(causal_validator, panel, ("source_identity", "schema_version"), "unknown")
    _assert_schema_rejects(causal_validator, panel, ("source_identity", "identity_basis"), "derived_exact_1520_rows")
    _assert_schema_rejects(causal_validator, panel, ("source_identity", "source_db_sha256"), None)
    _assert_schema_rejects(causal_validator, panel, ("source_identity", "source_db_sha256"), "A" * 64)
    _assert_schema_rejects_without_key(causal_validator, panel, ("source_identity", "source_db_sha256"))
    _assert_schema_rejects(causal_validator, panel, ("source_identity", "source_db_path"), str(tmp_path / "unknown.db"))
    _assert_schema_rejects(causal_validator, panel, ("source_identity", "source_db_path"), str(tmp_path / "Naver" / "_database" / "Stock_Database_ohlcv_5min.db"))
    _assert_schema_rejects(causal_validator, panel, ("source_identity", "source_tables", 0), "NAVER")
    _assert_schema_rejects(causal_validator, panel, ("audit", "unexpected"), True)
    _assert_schema_rejects(causal_validator, panel, ("audit", "exact_1520_source", "unexpected"), True)
    _assert_schema_rejects(causal_validator, panel, ("audit", "exact_1520_source", "source_db_paths", 0), str(tmp_path / "five_min.db"))
    _assert_schema_rejects(causal_validator, panel, ("audit", "source_audit", "forbidden_sources"), ["Naver"])
    _assert_schema_rejects(causal_validator, panel, ("horizon_days",), [1, 3])
    _assert_schema_rejects(causal_validator, panel, ("label_columns",), ["future_return_h1_1520_proxy", "future_return_h3_1520_proxy"])
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "symbol"), "00AB12")
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "observations", 0, "open"), 1.0)
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "observations", 0, "daily_close"), 1.0)
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "observations", 0, "final_close"), 1.0)
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "observations", 0, "one_day_close"), 1.0)
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "observations", 0, "feature_vector"), [1.0])
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "observations", 0, "feature_payload"), {"score": 1.0})
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "observations", 0, "source_db_path"), "_database/Stock_Database_ohlcv_1day.db")
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "observations", 0, "source_db_path"), "Naver")
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "observations", 0, "daily_amount"), 1.0)
    _assert_schema_rejects_without_key(causal_validator, panel, ("rows", 0, "labels", "future_return_h5_1520_proxy"))
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "labels", "future_return_h2_1520_proxy"), None)
    _assert_schema_rejects_without_key(causal_validator, panel, ("rows", 0, "future_return_h5_1520_proxy"))
    _assert_schema_rejects(causal_validator, panel, ("coverage", "labels", "future_return_h2_1520_proxy"), {"available": 0, "missing_entry": 0, "missing_exit": 0})
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "labels", "future_return_h1_1520_proxy"), None)
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "label_statuses", "future_return_h1_1520_proxy", "status"), "missing_exit")
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "exit_1520_by_label", "future_return_h1_1520_proxy"), None)
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "entry_1520", "timestamp_yyyymmddhhmm"), "202401021530")
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "entry_1520", "timestamp_yyyymmddhhmm"), 202401021520)
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "entry_1520", "amount_status"), "NOT_AVAILABLE")
    _assert_schema_rejects(causal_validator, panel, ("rows", 0, "entry_1520", "cumulative_volume_status"), "NOT_AVAILABLE")
