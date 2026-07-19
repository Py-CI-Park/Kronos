from __future__ import annotations

import copy
import importlib.util
import importlib.abc
import json
import socket
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl.korean_index_source import (  # noqa: E402
    NORMALIZED_ARTIFACT_FIELDS,
    PYKRX_PACKAGE_VERSION,
    RAW_ARTIFACT_FIELDS,
    KoreanIndexArtifactError,
    build_normalized_index_artifact,
    canonical_json_bytes,
    collect_index_artifacts,
    load_normalized_index_artifact,
    load_raw_index_artifact,
    validate_normalized_index_artifact,
    validate_korean_index_artifact,
    sha256_json,
    validate_raw_index_artifact,
    write_normalized_index_artifact,
    write_raw_index_artifact,
)

COLLECTED_AT = "2026-07-18T12:34:56Z"


def _provider_rows(*, market: str, index_code: str, index_name: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    assert market in {"KOSPI", "KOSDAQ"}
    assert index_name == market
    assert index_code == {"KOSPI": "1001", "KOSDAQ": "2001"}[market]
    assert start_date == "2024-01-02"
    assert end_date == "2024-01-05"
    return [
        {"date": "2024-01-02", "종가": 2600.25, "거래량": 1000},
        {"date": "2024-01-03", "종가": 2610.5, "거래량": 1100},
        {"date": "2024-01-05", "종가": 2622.75, "거래량": 1200},
    ]


def _artifacts(market: str = "KOSPI") -> dict[str, dict[str, Any]]:
    return collect_index_artifacts(
        market=market,
        start_date="2024-01-02",
        end_date="2024-01-05",
        provider=_provider_rows,
        collected_at=COLLECTED_AT,
    )


def _select_fields(artifact: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: artifact[field] for field in fields}


def _refresh_raw_hashes(artifact: dict[str, Any]) -> None:
    artifact["raw_sha256"] = sha256_json(_select_fields(artifact, RAW_ARTIFACT_FIELDS[:-2]))
    artifact["artifact_sha256"] = sha256_json(_select_fields(artifact, RAW_ARTIFACT_FIELDS[:-1]))


def _refresh_normalized_hashes(artifact: dict[str, Any]) -> None:
    artifact["normalized_sha256"] = sha256_json(_select_fields(artifact, NORMALIZED_ARTIFACT_FIELDS[:-3]))
    artifact["artifact_sha256"] = sha256_json(_select_fields(artifact, NORMALIZED_ARTIFACT_FIELDS[:-1]))


class _PykrxImportBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path: object, target: object = None) -> None:
        if fullname == "pykrx" or fullname.startswith("pykrx."):
            raise AssertionError("validation must not import pykrx")
        return None


def _block_pykrx_and_network(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(sys.modules):
        if name == "pykrx" or name.startswith("pykrx."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    blocker = _PykrxImportBlocker()
    monkeypatch.setattr(sys, "meta_path", [blocker, *sys.meta_path])

    def _no_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("validation must not access the network")

    monkeypatch.setattr(socket.socket, "connect", _no_connect)


def test_validation_is_offline_and_normalized_payload_matches_overlay_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_pykrx_and_network(monkeypatch)
    artifacts = _artifacts()
    raw_summary = validate_raw_index_artifact(artifacts["raw"])
    normalized_summary = validate_normalized_index_artifact(artifacts["normalized"], raw_artifact=artifacts["raw"])

    assert "pykrx" not in sys.modules
    assert normalized_summary["market"] == "KOSPI"
    assert normalized_summary["index_code"] == "1001"
    assert normalized_summary["series"] == [
        {"date": "2024-01-02", "close": 2600.25},
        {"date": "2024-01-03", "close": 2610.5},
        {"date": "2024-01-05", "close": 2622.75},
    ]
    assert normalized_summary["raw_sha256"] == raw_summary["raw_sha256"]
    assert set(normalized_summary) >= {"market", "series", "raw_sha256", "normalized_sha256", "artifact_sha256", "source_metadata"}
    metadata = normalized_summary["source_metadata"]
    assert metadata["naver_disabled"] is True
    assert metadata["no_live_fetch"] is True
    assert metadata["no_fallback"] is True
    assert metadata["no_interpolation"] is True
    assert metadata["official_close"] is False
    assert metadata["point_in_time_constituents"] is False


def test_public_validator_returns_exact_overlay_view_for_mapping_and_expected_market(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_pykrx_and_network(monkeypatch)
    normalized = _artifacts()["normalized"]

    view = validate_korean_index_artifact(normalized, expected_market="KOSPI")

    assert "pykrx" not in sys.modules
    assert view["market"] == "KOSPI"
    assert view["index_code"] == "1001"
    assert view["index_name"] == "KOSPI"
    assert view["series"] == [
        {"date": "2024-01-02", "close": 2600.25},
        {"date": "2024-01-03", "close": 2610.5},
        {"date": "2024-01-05", "close": 2622.75},
    ]
    assert set(view["false_locks"]) == {
        "official_close",
        "full_day_daily_ohlcv",
        "live_trading",
        "profit_claim",
        "paper_trading",
        "broker_integration",
        "model_build_allowed",
        "promotion_allowed",
        "go_summary_allowed",
        "live_broker_order_allowed",
    }
    assert set(view["claims"]) == {
        "official_close",
        "point_in_time_constituents",
        "live_trading",
        "profit",
        "paper_trading",
        "broker_integration",
    }
    assert all(value is False for value in view["false_locks"].values())
    assert all(value is False for value in view["claims"].values())
    assert "false_research_locks" not in view
    assert "no_claim_flags" not in view
    assert view["provider_package"] == normalized["provider_package"]
    assert view["package"] == normalized["provider_package"]
    assert view["parser"] == {
        "protocol_version": normalized["protocol_version"],
        "parser_version": normalized["parser_version"],
        "collector_version": normalized["collector_version"],
        "normalization_method": normalized["source_lineage"]["normalization_method"],
    }
    assert view["license_review"] == normalized["source_metadata"]["license_review"]
    assert view["point_in_time"] == {
        "constituents": False,
        "limitation": "index_levels_only_not_constituents",
        "index_levels_only": True,
    }
    assert view["hashes"] == {
        "raw_sha256": normalized["raw_sha256"],
        "normalized_sha256": normalized["normalized_sha256"],
        "artifact_sha256": normalized["artifact_sha256"],
    }


def test_public_validator_uses_content_addressed_loader_for_paths(tmp_path: Path) -> None:
    normalized = _artifacts()["normalized"]
    normalized_path = write_normalized_index_artifact(tmp_path, normalized)

    view = validate_korean_index_artifact(normalized_path, expected_market="KOSPI")

    assert view["artifact_sha256"] == normalized["artifact_sha256"]
    wrong_name = tmp_path / "korean-index-kospi-normalized-not-content-addressed.json"
    wrong_name.write_bytes(canonical_json_bytes(normalized) + b"\n")
    with pytest.raises(KoreanIndexArtifactError, match="filename does not match content-addressed"):
        validate_korean_index_artifact(wrong_name, expected_market="KOSPI")


def test_public_validator_enforces_expected_market_tamper_policy_and_exact_lock_claim_sets() -> None:
    normalized = _artifacts()["normalized"]

    with pytest.raises(KoreanIndexArtifactError, match="market mismatch"):
        validate_korean_index_artifact(normalized, expected_market="KOSDAQ")
    with pytest.raises(KoreanIndexArtifactError, match="expected_market must be canonical"):
        validate_korean_index_artifact(normalized, expected_market="kospi")

    tampered = copy.deepcopy(normalized)
    tampered["series"][0]["close"] = 9999.0
    with pytest.raises(KoreanIndexArtifactError, match="normalized_sha256 mismatch"):
        validate_korean_index_artifact(tampered, expected_market="KOSPI")

    policy_mismatch = copy.deepcopy(normalized)
    policy_mismatch["source_lineage"]["fallback_used"] = True
    with pytest.raises(KoreanIndexArtifactError, match="fallback_used"):
        validate_korean_index_artifact(policy_mismatch, expected_market="KOSPI")

    extra_lock = copy.deepcopy(normalized)
    extra_lock["false_research_locks"]["extra_lock"] = False
    with pytest.raises(KoreanIndexArtifactError, match="false_research_locks"):
        validate_korean_index_artifact(extra_lock, expected_market="KOSPI")

    missing_claim = copy.deepcopy(normalized)
    missing_claim["no_claim_flags"].pop("fallback_claim")
    with pytest.raises(KoreanIndexArtifactError, match="no_claim_flags"):
        validate_korean_index_artifact(missing_claim, expected_market="KOSPI")



def test_mock_collection_writes_content_addressed_immutable_artifacts_and_detects_tamper(tmp_path: Path) -> None:
    artifacts = _artifacts()
    raw_path = write_raw_index_artifact(tmp_path, artifacts["raw"])
    normalized_path = write_normalized_index_artifact(tmp_path, artifacts["normalized"])

    assert artifacts["raw"]["artifact_sha256"] in raw_path.name
    assert artifacts["normalized"]["artifact_sha256"] in normalized_path.name
    assert load_raw_index_artifact(raw_path) == artifacts["raw"]
    assert load_normalized_index_artifact(normalized_path) == artifacts["normalized"]

    with pytest.raises(FileExistsError):
        write_normalized_index_artifact(tmp_path, artifacts["normalized"])

    tampered = json.loads(normalized_path.read_text(encoding="utf-8"))
    tampered["series"][0]["close"] = 9999.0
    normalized_path.write_bytes(canonical_json_bytes(tampered) + b"\n")
    with pytest.raises(KoreanIndexArtifactError, match="normalized_sha256 mismatch"):
        load_normalized_index_artifact(normalized_path)


def test_metadata_versions_dates_no_naver_no_fallback_and_exact_market_ids() -> None:
    kospi = _artifacts("KOSPI")["normalized"]
    kosdaq = _artifacts("KOSDAQ")["normalized"]

    assert kospi["index_code"] == "1001"
    assert kosdaq["index_code"] == "2001"
    for artifact in (kospi, kosdaq):
        metadata = artifact["source_metadata"]
        assert artifact["provider_package"] == {
            "name": "pykrx",
            "version": PYKRX_PACKAGE_VERSION,
            "required_version": PYKRX_PACKAGE_VERSION,
        }
        assert metadata["source_package"]["version"] == PYKRX_PACKAGE_VERSION
        assert metadata["license_review"] == {
            "status": "not_reviewed_for_redistribution",
            "review_date": "2026-07-18",
            "notes": "Local research custody of pykrx-derived KRX index levels only; no redistribution-rights or unsupported licensing claim is made.",
            "unsupported_redistribution_claim": False,
        }
        assert metadata["naver_disabled"] is True
        assert metadata["fallback_enabled"] is False
        assert metadata["fallback_sources"] == []
        assert metadata["point_in_time_limitation"] == "index_levels_only_not_constituents"
        assert all(value is False for value in artifact["false_research_locks"].values())
        assert all(value is False for value in artifact["six_locks_false"].values())
        assert all(value is False for value in artifact["no_claim_flags"].values())

    with pytest.raises(KoreanIndexArtifactError, match="pykrx package version must be exactly"):
        collect_index_artifacts(
            market="KOSPI",
            start_date="2024-01-02",
            end_date="2024-01-05",
            provider=_provider_rows,
            provider_package_version="1.2.7",
            collected_at=COLLECTED_AT,
        )


def test_validation_rejects_tampered_hash_order_level_policy_and_leading_coverage() -> None:
    normalized = _artifacts()["normalized"]

    bad_code = copy.deepcopy(normalized)
    bad_code["index_code"] = "2001"
    with pytest.raises(KoreanIndexArtifactError, match="KOSPI index_code"):
        validate_normalized_index_artifact(bad_code)

    duplicate_date = copy.deepcopy(normalized)
    duplicate_date["series"][1]["date"] = "2024-01-02"
    with pytest.raises(KoreanIndexArtifactError, match="strictly ascending"):
        validate_normalized_index_artifact(duplicate_date)

    non_positive = copy.deepcopy(normalized)
    non_positive["series"][0]["close"] = 0.0
    with pytest.raises(KoreanIndexArtifactError, match="positive finite"):
        validate_normalized_index_artifact(non_positive)

    raw_hash = copy.deepcopy(normalized)
    raw_hash["raw_sha256"] = "0" * 64
    with pytest.raises(KoreanIndexArtifactError, match="artifact_sha256 mismatch|normalized_sha256 mismatch|raw hash mismatch"):
        validate_normalized_index_artifact(raw_hash)

    naver_enabled = copy.deepcopy(normalized)
    naver_enabled["source_metadata"]["naver_disabled"] = False
    with pytest.raises(KoreanIndexArtifactError, match="naver_disabled"):
        validate_normalized_index_artifact(naver_enabled)

    fallback_enabled = copy.deepcopy(normalized)
    fallback_enabled["source_metadata"]["fallback_enabled"] = True
    with pytest.raises(KoreanIndexArtifactError, match="fallback_enabled"):
        validate_normalized_index_artifact(fallback_enabled)

    bad_leading = copy.deepcopy(normalized)
    bad_leading["actual_start_date"] = "2024-01-03"
    with pytest.raises(KoreanIndexArtifactError, match="actual coverage|source_lineage"):
        validate_normalized_index_artifact(bad_leading)


def test_source_lineage_fields_are_exact_even_with_recomputed_hashes() -> None:
    artifacts = _artifacts()

    raw_extra = copy.deepcopy(artifacts["raw"])
    raw_extra["source_lineage"]["naver_snapshot_url"] = "https://naver.example/index"
    raw_extra["source_metadata"]["source_lineage"]["lineage"] = copy.deepcopy(raw_extra["source_lineage"])
    _refresh_raw_hashes(raw_extra)
    with pytest.raises(KoreanIndexArtifactError, match="source_lineage fields are not canonical"):
        validate_raw_index_artifact(raw_extra)

    normalized_extra = copy.deepcopy(artifacts["normalized"])
    normalized_extra["source_lineage"]["fallback_sources"] = ["naver"]
    normalized_extra["source_metadata"]["source_lineage"]["lineage"] = copy.deepcopy(normalized_extra["source_lineage"])
    _refresh_normalized_hashes(normalized_extra)
    with pytest.raises(KoreanIndexArtifactError, match="source_lineage fields are not canonical"):
        validate_normalized_index_artifact(normalized_extra)

    metadata_extra = copy.deepcopy(artifacts["normalized"])
    metadata_extra["source_metadata"]["source_lineage"]["naver_snapshot_url"] = "https://naver.example/index"
    _refresh_normalized_hashes(metadata_extra)
    with pytest.raises(KoreanIndexArtifactError, match="source_metadata.source_lineage fields are not canonical"):
        validate_normalized_index_artifact(metadata_extra)


def test_embedded_source_metadata_lineage_must_match_top_level_with_recomputed_hashes() -> None:
    artifacts = _artifacts()

    raw_mismatch = copy.deepcopy(artifacts["raw"])
    raw_mismatch["source_metadata"]["source_lineage"]["lineage"]["fallback_used"] = True
    _refresh_raw_hashes(raw_mismatch)
    with pytest.raises(KoreanIndexArtifactError, match="source_metadata.source_lineage.lineage"):
        validate_raw_index_artifact(raw_mismatch)

    normalized_mismatch = copy.deepcopy(artifacts["normalized"])
    normalized_mismatch["source_metadata"]["source_lineage"]["lineage"]["fallback_used"] = True
    _refresh_normalized_hashes(normalized_mismatch)
    with pytest.raises(KoreanIndexArtifactError, match="source_metadata.source_lineage.lineage"):
        validate_normalized_index_artifact(normalized_mismatch)


def test_collector_cli_import_and_parser_are_lazy_and_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_pykrx_and_network(monkeypatch)
    script_path = REPO_ROOT / "scripts" / "collect_korean_index_artifact.py"
    spec = importlib.util.spec_from_file_location("kronos_collect_korean_index_artifact", script_path)
    assert spec is not None and spec.loader is not None
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    args = collector.parse_args(
        ["--market", "KOSPI", "--start-date", "2024-01-02", "--end-date", "2024-01-05", "--output-dir", "out"]
    )

    assert args.market == "KOSPI"
    assert args.start_date == "2024-01-02"
    assert args.end_date == "2024-01-05"
    assert args.output_dir == "out"
    assert "pykrx" not in sys.modules
    with pytest.raises(SystemExit):
        collector.parse_args(["--market", "KOSPI", "--start-date", "2024-01-02", "--end-date", "2024-01-05"])


def test_raw_provider_rows_must_be_ordered_unique_positive_and_in_range() -> None:
    with pytest.raises(KoreanIndexArtifactError, match="strictly ascending"):
        collect_index_artifacts(
            market="KOSPI",
            start_date="2024-01-02",
            end_date="2024-01-05",
            provider=lambda **_: [
                {"date": "2024-01-03", "종가": 2610.5},
                {"date": "2024-01-02", "종가": 2600.25},
            ],
            collected_at=COLLECTED_AT,
        )
    with pytest.raises(KoreanIndexArtifactError, match="outside requested"):
        collect_index_artifacts(
            market="KOSPI",
            start_date="2024-01-02",
            end_date="2024-01-05",
            provider=lambda **_: [{"date": "2024-01-08", "종가": 2600.25}],
            collected_at=COLLECTED_AT,
        )
    with pytest.raises(KoreanIndexArtifactError, match="positive finite"):
        collect_index_artifacts(
            market="KOSPI",
            start_date="2024-01-02",
            end_date="2024-01-05",
            provider=lambda **_: [{"date": "2024-01-02", "종가": float("nan")}],
            collected_at=COLLECTED_AT,
        )


def test_normalized_rebuild_is_exact_raw_lineage() -> None:
    raw = _artifacts()["raw"]
    normalized = build_normalized_index_artifact(raw)
    summary = validate_normalized_index_artifact(normalized, raw_artifact=raw)

    assert summary["series"] == [{"date": row["date"], "close": row["close"]} for row in raw["raw_rows"]]
    assert normalized["source_lineage"]["source_raw_sha256"] == raw["raw_sha256"]
    assert normalized["source_lineage"]["source_artifact_sha256"] == raw["artifact_sha256"]
    assert normalized["source_lineage"]["source_artifact_filename"].startswith("korean-index-kospi-raw-")
