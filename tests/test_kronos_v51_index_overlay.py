from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from stom_rl import korean_index_overlay as kio
from stom_rl.korean_index_source import (
    build_normalized_index_artifact,
    build_raw_index_artifact,
    validate_korean_index_artifact,
    write_normalized_index_artifact,
)


COLLECTED_AT = "2026-07-18T12:34:56Z"


def _artifact(market: str, rows: list[tuple[str, object]]) -> dict[str, Any]:
    raw = build_raw_index_artifact(
        market=market,
        start_date=rows[0][0],
        end_date=rows[-1][0],
        raw_rows=[{"date": date, "종가": close} for date, close in rows],
        collected_at=COLLECTED_AT,
    )
    return build_normalized_index_artifact(raw)


def _rl(rows: list[tuple[str, object]], **overrides: object) -> dict[str, object]:
    price_basis = overrides.pop("price_basis", kio.PRICE_BASIS)
    official_close = overrides.pop("official_close", False)
    payload: dict[str, object] = {
        "source_id": "rl-h1-economic-nav",
        "price_basis": price_basis,
        "official_close": official_close,
        "source_metadata": {
            "source_kind": "v51_accounting",
            "price_basis": price_basis,
            "official_close": official_close,
        },
        "series": [
            {
                "date": date,
                "account_nav_krw": value,
                "price_basis": price_basis,
                "official_close": official_close,
            }
            for date, value in rows
        ],
    }
    payload.update(overrides)
    return payload


def _good_artifacts() -> dict[str, dict[str, Any]]:
    return {
        "KOSPI": _artifact(
            "KOSPI",
            [
                ("2024-01-02", 90),
                ("2024-01-03", 100),
                ("2024-01-04", 110),
                ("2024-01-05", 120),
            ],
        ),
        "KOSDAQ": _artifact(
            "KOSDAQ",
            [
                ("2024-01-03", 200),
                ("2024-01-04", 220),
                ("2024-01-05", 260),
                ("2024-01-08", 300),
            ],
        ),
    }


def _good_rl() -> dict[str, object]:
    return _rl(
        [
            ("2024-01-03", 60_000_000),
            ("2024-01-04", 63_000_000),
            ("2024-01-05", 66_000_000),
            ("2024-01-09", 67_000_000),
        ]
    )


def _blocked_reasons(
    kospi_source: object,
    kosdaq_source: object,
    rl_payload: dict[str, object],
    *,
    min_common_dates: int = 2,
) -> list[str]:
    result = kio.build_korean_index_overlay_result(
        kospi_source,
        kosdaq_source,
        rl_payload,
        min_common_dates=min_common_dates,
    )
    assert result["status"] == "BLOCKED"
    assert result["false_locks"] == validate_korean_index_artifact(_good_artifacts()["KOSPI"])["false_locks"]
    assert result["claims"] == validate_korean_index_artifact(_good_artifacts()["KOSPI"])["claims"]
    assert result["source_policy"]["naver_disabled"] is True
    assert result["source_policy"]["no_live_fetch"] is True
    assert result["source_policy"]["no_fallback"] is True
    assert result["coverage"]["nearest_date_matches"] == []
    kio.validate_korean_index_overlay(result)
    return result["reason_codes"]


def test_overlay_uses_source_validator_for_path_and_mapping_with_exact_intersection(tmp_path: Path) -> None:
    artifacts = _good_artifacts()
    kospi_path = write_normalized_index_artifact(tmp_path, artifacts["KOSPI"])

    overlay = kio.build_korean_index_overlay(kospi_path, artifacts["KOSDAQ"], _good_rl())

    assert kio.validate_korean_index_overlay(overlay) is overlay
    assert overlay["schema_version"] == kio.SCHEMA_VERSION
    assert overlay["status"] == "PASS"
    assert overlay["price_basis"] == kio.PRICE_BASIS
    assert overlay["causal_cutoff_kst"] == kio.CAUSAL_CUTOFF_KST
    assert overlay["official_close"] is False
    assert overlay["network_used"] is False
    assert overlay["source_policy"]["offline_artifacts_only"] is True
    assert overlay["source_policy"]["naver_disabled"] is True
    assert overlay["source_policy"]["no_interpolation"] is True
    assert overlay["source_policy"]["no_nearest_date"] is True
    assert overlay["point_in_time_constituents"] is False
    assert overlay["false_locks"] == validate_korean_index_artifact(artifacts["KOSPI"])["false_locks"]
    assert overlay["claims"] == validate_korean_index_artifact(artifacts["KOSPI"])["claims"]

    coverage = overlay["coverage"]
    assert coverage["common_dates"] == ["2024-01-03", "2024-01-04", "2024-01-05"]
    assert coverage["common_date_count"] == 3
    assert coverage["input_counts"] == {"KOSPI": 4, "KOSDAQ": 4, "RL": 4}
    assert coverage["dropped_dates"] == {
        "KOSPI": ["2024-01-02"],
        "KOSDAQ": ["2024-01-08"],
        "RL": ["2024-01-09"],
    }
    assert coverage["dropped_date_count"] == {"KOSPI": 1, "KOSDAQ": 1, "RL": 1}
    assert coverage["filled_dates"] == []
    assert coverage["interpolated_dates"] == []
    assert coverage["nearest_date_matches"] == []

    by_id = {series["id"]: series for series in overlay["series"]}
    assert [row["close"] for row in by_id["KOSPI"]["series"]] == [
        "100.000000000000",
        "110.000000000000",
        "120.000000000000",
    ]
    assert [row["close"] for row in by_id["KOSDAQ"]["series"]] == [
        "100.000000000000",
        "110.000000000000",
        "130.000000000000",
    ]
    assert [row["close"] for row in by_id["RL"]["series"]] == [
        "100.000000000000",
        "105.000000000000",
        "110.000000000000",
    ]
    assert by_id["KOSPI"]["normalization_start_date"] == "2024-01-03"
    assert by_id["KOSPI"]["normalization_start_close"] == "100"
    assert overlay["source_artifact_hashes"]["KOSPI"]["raw_sha256"] == artifacts["KOSPI"]["raw_sha256"]
    assert overlay["source_artifacts"]["KOSPI"]["artifact_path"] == str(kospi_path)
    assert "artifact_path" not in overlay["source_artifacts"]["KOSDAQ"]
    assert overlay["source_artifacts"]["KOSPI"]["source_metadata"]["provider"] == "pykrx"
    assert overlay["source_artifacts"]["KOSPI"]["source_metadata"]["point_in_time_constituents"] is False
    assert overlay["source_artifacts"]["KOSPI"]["provider_package"] == artifacts["KOSPI"]["provider_package"]
    assert overlay["source_artifacts"]["KOSPI"]["parser"]["parser_version"] == artifacts["KOSPI"]["parser_version"]
    assert overlay["source_artifacts"]["KOSPI"]["license_review"] == artifacts["KOSPI"]["source_metadata"]["license_review"]
    assert overlay["source_artifacts"]["KOSPI"]["point_in_time"] == {
        "constituents": False,
        "limitation": "index_levels_only_not_constituents",
        "index_levels_only": True,
    }
    assert overlay["overlay_sha256"] == kio.sha256_hex({key: value for key, value in overlay.items() if key != "overlay_sha256"})


def test_overlay_accepts_validated_mapping_sources_without_raw_mapping_bypass() -> None:
    artifacts = _good_artifacts()

    overlay = kio.build_korean_index_overlay(artifacts["KOSPI"], artifacts["KOSDAQ"], _good_rl())

    assert overlay["status"] == "PASS"
    assert overlay["source_artifact_hashes"]["KOSPI"]["artifact_sha256"] == artifacts["KOSPI"]["artifact_sha256"]
    assert overlay["source_artifact_hashes"]["KOSDAQ"]["artifact_sha256"] == artifacts["KOSDAQ"]["artifact_sha256"]


def test_overlay_allows_honest_daily_close_v51_accounting_source_name() -> None:
    artifacts = _good_artifacts()
    rows = [("2024-01-03", 60_000_000), ("2024-01-04", 61_000_000), ("2024-01-05", 62_000_000)]

    overlay = kio.build_korean_index_overlay(
        artifacts["KOSPI"],
        artifacts["KOSDAQ"],
        _rl(
            rows,
            source_id="daily-close-v51-accounting",
            source_metadata={
                "source_kind": "daily-close-v51-accounting",
                "price_basis": kio.PRICE_BASIS,
                "official_close": False,
            },
        ),
    )

    assert overlay["status"] == "PASS"
    assert overlay["series"][2]["source"]["source_label"] == "daily-close-v51-accounting"


def test_tampered_source_artifact_hash_fails_closed_and_strict_api_raises() -> None:
    artifacts = _good_artifacts()
    tampered = copy.deepcopy(artifacts["KOSPI"])
    tampered["artifact_sha256"] = "0" * 64
    reasons = _blocked_reasons(tampered, artifacts["KOSDAQ"], _good_rl())

    assert reasons == [kio.INDEX_ARTIFACT_HASH_MISMATCH]
    with pytest.raises(kio.KoreanIndexOverlayError) as excinfo:
        kio.build_korean_index_overlay(tampered, artifacts["KOSDAQ"], _good_rl())
    assert excinfo.value.reason_codes == (kio.INDEX_ARTIFACT_HASH_MISMATCH,)


def test_missing_and_invalid_artifacts_fail_closed(tmp_path: Path) -> None:
    artifacts = _good_artifacts()
    assert kio.INDEX_ARTIFACT_MISSING in _blocked_reasons(tmp_path / "missing.json", artifacts["KOSDAQ"], _good_rl())

    assert kio.INDEX_ARTIFACT_INVALID in _blocked_reasons({"bad": "schema"}, artifacts["KOSDAQ"], _good_rl())


def test_no_and_too_short_exact_intersections_fail_closed() -> None:
    kospi = _artifact("KOSPI", [("2024-01-02", 100), ("2024-01-03", 101)])
    kosdaq = _artifact("KOSDAQ", [("2024-01-04", 200), ("2024-01-05", 201)])
    assert kio.NO_COMMON_DATES in _blocked_reasons(kospi, kosdaq, _rl([("2024-01-08", 60_000_000)]))

    kospi = _artifact("KOSPI", [("2024-01-02", 100), ("2024-01-03", 101)])
    kosdaq = _artifact("KOSDAQ", [("2024-01-03", 200), ("2024-01-04", 201)])
    assert kio.TOO_SHORT_INTERSECTION in _blocked_reasons(
        kospi,
        kosdaq,
        _rl([("2024-01-03", 60_000_000), ("2024-01-08", 61_000_000)]),
    )


def test_mismatched_market_ids_fail_closed() -> None:
    artifacts = _good_artifacts()

    assert kio.INDEX_ARTIFACT_MARKET_MISMATCH in _blocked_reasons(
        artifacts["KOSDAQ"],
        artifacts["KOSDAQ"],
        _good_rl(),
    )


def test_duplicate_dates_fail_closed_for_index_and_rl_series() -> None:
    artifacts = _good_artifacts()
    duplicate = copy.deepcopy(artifacts["KOSPI"])
    duplicate["series"][1]["date"] = "2024-01-02"

    assert kio.INDEX_ARTIFACT_DUPLICATE_DATES in _blocked_reasons(duplicate, artifacts["KOSDAQ"], _good_rl())
    assert kio.RL_NAV_DUPLICATE_DATES in _blocked_reasons(
        artifacts["KOSPI"],
        artifacts["KOSDAQ"],
        _rl([("2024-01-03", 60_000_000), ("2024-01-03", 61_000_000)]),
    )


def test_nonpositive_values_fail_closed_for_index_and_rl_series() -> None:
    artifacts = _good_artifacts()
    nonpositive = copy.deepcopy(artifacts["KOSPI"])
    nonpositive["series"][0]["close"] = 0

    assert kio.NONPOSITIVE_SERIES_VALUE in _blocked_reasons(nonpositive, artifacts["KOSDAQ"], _good_rl())
    assert kio.NONPOSITIVE_SERIES_VALUE in _blocked_reasons(
        artifacts["KOSPI"],
        artifacts["KOSDAQ"],
        _rl([("2024-01-03", 0), ("2024-01-04", 60_000_000)]),
    )


def test_rl_full_day_daily_ohlcv_or_official_close_sources_fail_closed() -> None:
    artifacts = _good_artifacts()
    rows = [("2024-01-03", 60_000_000), ("2024-01-04", 61_000_000)]

    assert kio.RL_NAV_DAILY_OR_OFFICIAL_CLOSE_SOURCE in _blocked_reasons(
        artifacts["KOSPI"], artifacts["KOSDAQ"], _rl(rows, price_basis="daily_ohlcv_close")
    )
    assert kio.RL_NAV_DAILY_OR_OFFICIAL_CLOSE_SOURCE in _blocked_reasons(
        artifacts["KOSPI"], artifacts["KOSDAQ"], _rl(rows, official_close=True)
    )
    for payload in (
        _rl(rows, source_id="full-day-policy-run"),
        _rl(rows, source_id="daily_ohlcv-policy-run"),
        _rl(rows, source_id="daily-ohlcv-policy-run"),
        _rl(rows, run_id="experiment-1day-source"),
        _rl(rows, source_id="official-close-ablation"),
        _rl(rows, source_path="D:/cache/naver/rl_nav.json"),
    ):
        assert kio.RL_NAV_DAILY_OR_OFFICIAL_CLOSE_SOURCE in _blocked_reasons(
            artifacts["KOSPI"], artifacts["KOSDAQ"], payload
        )


def test_naver_or_point_in_time_index_claims_fail_closed() -> None:
    artifacts = _good_artifacts()
    naver = copy.deepcopy(artifacts["KOSPI"])
    naver["source_metadata"]["naver_disabled"] = False
    assert kio.INDEX_ARTIFACT_FORBIDDEN_SOURCE in _blocked_reasons(naver, artifacts["KOSDAQ"], _good_rl())

    point_in_time = copy.deepcopy(artifacts["KOSPI"])
    point_in_time["source_metadata"]["point_in_time_constituents"] = True
    assert kio.POINT_IN_TIME_CONSTITUENT_CLAIM in _blocked_reasons(point_in_time, artifacts["KOSDAQ"], _good_rl())


def test_source_and_overlay_lock_claim_sets_must_be_exact() -> None:
    artifacts = _good_artifacts()

    extra_lock = copy.deepcopy(artifacts["KOSPI"])
    extra_lock["false_research_locks"]["extra"] = False
    assert kio.INDEX_ARTIFACT_INVALID in _blocked_reasons(extra_lock, artifacts["KOSDAQ"], _good_rl())

    missing_claim = copy.deepcopy(artifacts["KOSPI"])
    missing_claim["no_claim_flags"].pop("fallback_claim")
    assert kio.INDEX_ARTIFACT_INVALID in _blocked_reasons(missing_claim, artifacts["KOSDAQ"], _good_rl())

    overlay = kio.build_korean_index_overlay(artifacts["KOSPI"], artifacts["KOSDAQ"], _good_rl())
    tampered_overlay = copy.deepcopy(overlay)
    tampered_overlay["false_locks"]["extra"] = False
    tampered_overlay["overlay_sha256"] = kio.sha256_hex(
        {key: value for key, value in tampered_overlay.items() if key != "overlay_sha256"}
    )
    with pytest.raises(kio.KoreanIndexOverlayError) as excinfo:
        kio.validate_korean_index_overlay(tampered_overlay)
    assert excinfo.value.reason_codes == (kio.INDEX_ARTIFACT_INVALID,)
