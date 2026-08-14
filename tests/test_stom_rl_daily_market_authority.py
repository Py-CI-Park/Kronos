from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from stom_rl.daily_market_authority_artifacts import (
    AuthorityDashboardSummary,
    write_authority_artifacts,
)
from stom_rl.daily_market_authority_audit import (
    MarketAuthorityInputs,
    audit_market_authority,
)
from stom_rl.daily_market_authority_contract import (
    DailyMarketAuthorityError,
    MarketAuthorityReceipt,
)


def _daily_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        create_sql = (
            'CREATE TABLE "A005930" ('
            + "date INTEGER, open REAL, high REAL, low REAL, close REAL, volume REAL, "
            + '"상장주식수" REAL, "외국인주문한도수량" REAL, "외국인현보유수량" REAL, '
            + '"외국인현보유비율" REAL, "기관순매수" REAL, "기관누적순매수" REAL)'
        )
        _ = connection.execute(create_sql)
        _ = connection.execute(
            'INSERT INTO "A005930" VALUES '
            + "(20260102, 70000, 71000, 69000, 70500, 1000, 1, 1, 1, 1, 1, 1)"
        )


def _stockinfo_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        _ = connection.execute(
            'CREATE TABLE stockinfo ("index" TEXT, "종목명" TEXT, "코스닥" INTEGER)'
        )
        _ = connection.execute('INSERT INTO stockinfo VALUES ("005930", "삼성전자", 0)')


def _candidate_scores(path: Path, *, eligibility: str = "True") -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("date", "code", "eligible_for_selection", "table")
        )
        writer.writeheader()
        writer.writerow(
            {
                "date": "20260102",
                "code": "005930",
                "eligible_for_selection": eligibility,
                "table": "A005930",
            }
        )


def _inputs(tmp_path: Path) -> MarketAuthorityInputs:
    tmp_path.mkdir(parents=True, exist_ok=True)
    daily = tmp_path / "daily.db"
    stockinfo = tmp_path / "stockinfo.db"
    scores = tmp_path / "scores.csv"
    _daily_database(daily)
    _stockinfo_database(stockinfo)
    _candidate_scores(scores)
    trust_store = tmp_path / "reviewer_trust.json"
    _ = trust_store.write_bytes(
        b'{"keys":[],"schema":"kronos_daily_market_reviewer_trust.v1"}'
    )
    return MarketAuthorityInputs(
        daily,
        stockinfo,
        scores,
        tmp_path / "price_provenance.json",
        tmp_path / "krx_current.csv",
        tmp_path / "pit_membership.csv",
        tmp_path / "authority_sources",
        trust_store,
        tmp_path / "authority_reviews",
    )


def test_authority_and_model_share_strict_candidate_eligibility_tokens(
    tmp_path: Path,
) -> None:
    accepted = _inputs(tmp_path / "accepted")
    _candidate_scores(accepted.candidate_scores, eligibility="1")

    receipt = audit_market_authority(accepted)

    assert receipt.d1_universe.required_membership_pairs == 1

    invalid = _inputs(tmp_path / "invalid")
    _candidate_scores(invalid.candidate_scores, eligibility="yes")
    with pytest.raises(
        DailyMarketAuthorityError,
        match="CANDIDATE_ELIGIBILITY_INVALID",
    ):
        _ = audit_market_authority(invalid)


def _source_artifact(inputs: MarketAuthorityInputs, payload: bytes) -> str:
    source_hash = hashlib.sha256(payload).hexdigest()
    inputs.source_artifact_root.mkdir(exist_ok=True)
    _ = (inputs.source_artifact_root / f"{source_hash}.source").write_bytes(payload)
    return source_hash


def _write_price_provenance(inputs: MarketAuthorityInputs) -> None:
    database_hash = hashlib.sha256(inputs.daily_database.read_bytes()).hexdigest()
    source_hash = _source_artifact(inputs, b"kiwoom-opt10081-reviewed-fixture")
    _ = inputs.price_provenance.write_text(
        json.dumps(
            {
                "schema_version": "kronos_price_provenance.v1",
                "database_sha256": database_hash,
                "source_system": "KIWOOM_OPENAPI_OPT10081",
                "source_field": "수정주가구분",
                "price_basis": "split_adjusted",
                "collection_option": "adjusted_price_enabled",
                "corporate_action_policy": "split_adjusted_dividend_excluded",
                "source_sha256": source_hash,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_authority_audit_blocks_missing_price_and_pit_evidence(tmp_path: Path) -> None:
    # Given: usable local DBs without independent price or PIT provenance.
    inputs = _inputs(tmp_path)

    # When: the authority audit observes the sources read-only.
    receipt = audit_market_authority(inputs)

    # Then: data use remains research-only and both authority blockers stay visible.
    assert receipt.status == "BLOCKED_DATA_AUTHORITY"
    assert receipt.d0_price_basis.state == "BLOCKED"
    assert receipt.d0_price_basis.provenance_state == "MISSING"
    assert receipt.d0_price_basis.price_basis == "unknown"
    assert receipt.d1_universe.state == "BLOCKED"
    assert receipt.d1_universe.current_metadata_state == "MISSING"
    assert receipt.d1_universe.pit_membership_state == "MISSING"
    assert receipt.d1_universe.daily_table_count == 1
    assert receipt.d1_universe.required_membership_pairs == 1
    assert receipt.d1_universe.covered_membership_pairs == 0
    assert receipt.blockers == (
        "D0_PRICE_BASIS_NOT_VERIFIED",
        "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED",
    )
    assert receipt.historical_test_state == (
        "FEATURES_PARSED_REWARDS_PRICES_ACTION_EVALUATION_NOT_READ_CONTAMINATED"
    )
    assert receipt.fresh_oos_read is False


def test_authority_audit_keeps_content_bound_sources_blocked_without_signed_review(
    tmp_path: Path,
) -> None:
    # Given: price provenance bound to the DB plus PIT membership available before decision time.
    inputs = _inputs(tmp_path)
    with sqlite3.connect(inputs.daily_database) as connection:
        _ = connection.execute(
            'ALTER TABLE "A005930" ADD COLUMN "수정주가구분" INTEGER'
        )
    _write_price_provenance(inputs)
    krx_source_hash = _source_artifact(inputs, b"krx-dated-listed-products-fixture")
    _ = inputs.current_official_metadata.write_text(
        "code,name,market,instrument_type,available_at,source_hash\n"
        + f"005930,삼성전자,KOSPI,common_equity,20260101,{krx_source_hash}\n",
        encoding="utf-8",
    )
    _ = inputs.pit_membership.write_text(
        "code,name,market,instrument_type,effective_from,effective_to,available_at,source_hash\n"
        + f"005930,삼성전자,KOSPI,common_equity,20000101,20991231,20260101,{krx_source_hash}\n",
        encoding="utf-8",
    )

    # When: all required evidence is audited.
    receipt = audit_market_authority(inputs)

    # Then: byte identity alone cannot impersonate a signed Kiwoom/KRX review.
    assert receipt.status == "BLOCKED_DATA_AUTHORITY"
    assert receipt.d0_price_basis.state == "BLOCKED"
    assert receipt.d0_price_basis.price_basis == "unknown"
    assert receipt.d1_universe.state == "BLOCKED"
    assert receipt.d1_universe.coverage_percent == 100.0
    assert receipt.blockers == (
        "D0_PRICE_BASIS_NOT_VERIFIED",
        "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED",
    )
    assert receipt.promotion_allowed is False
    assert len(receipt.input_bindings) == 6
    assert len(receipt.source_artifacts) == 2
    assert receipt.d0_price_basis.checks[-1].check_id == (
        "PROVENANCE_SOURCE_REVIEW_VERIFIED"
    )
    assert receipt.d0_price_basis.checks[-1].passed is False
    assert receipt.d1_universe.checks[-1].passed is False


def test_authority_receipt_rejects_forged_verified_state(tmp_path: Path) -> None:
    receipt = audit_market_authority(_inputs(tmp_path))
    forged = receipt.model_dump(mode="json")
    forged["status"] = "VERIFIED_RESEARCH_DATA_AUTHORITY"
    forged["d0_price_basis"]["state"] = "VERIFIED"
    forged["d1_universe"]["state"] = "VERIFIED"
    forged["blockers"] = []

    with pytest.raises(ValidationError, match="verified"):
        _ = MarketAuthorityReceipt.model_validate(forged)


def test_historical_v2_blocked_wire_remains_readable_but_cannot_be_verified() -> None:
    wire = (
        Path(__file__).parent / "fixtures" / "daily_market_authority_002_blocked.json"
    ).read_bytes()
    parsed = MarketAuthorityReceipt.model_validate_json(wire)

    assert parsed.schema_version == "kronos_daily_market_authority.v2"
    assert parsed.status == "BLOCKED_DATA_AUTHORITY"
    forged = parsed.model_dump(mode="json")
    forged["schema_version"] = "kronos_daily_market_authority.v2"
    forged["status"] = "VERIFIED_RESEARCH_DATA_AUTHORITY"
    forged["d0_price_basis"] = {
        **forged["d0_price_basis"],
        "state": "VERIFIED",
    }
    forged["d1_universe"] = {
        **forged["d1_universe"],
        "state": "VERIFIED",
    }
    forged["blockers"] = []
    for field in (
        "verified_at_utc",
        "reviewer_trust_store_sha256",
        "reviewer_trust_store",
        "signed_extraction_reviews",
    ):
        del forged[field]
    with pytest.raises(ValidationError, match="legacy authority receipt"):
        _ = MarketAuthorityReceipt.model_validate(forged)


def test_authority_audit_rejects_provenance_when_local_basis_field_is_missing(
    tmp_path: Path,
) -> None:
    # Given: a matching provenance JSON but no price-basis field in the local DB.
    inputs = _inputs(tmp_path)
    _write_price_provenance(inputs)

    # When: local schema and external provenance are evaluated together.
    receipt = audit_market_authority(inputs)

    # Then: the unverifiable local lineage keeps D0 blocked.
    assert receipt.d0_price_basis.state == "BLOCKED"
    assert receipt.d0_price_basis.provenance_state == "PRESENT"
    assert receipt.d0_price_basis.checks[0].passed is False


def test_authority_audit_rejects_membership_published_after_decision(
    tmp_path: Path,
) -> None:
    # Given: a PIT row whose availability occurs after the model decision date.
    inputs = _inputs(tmp_path)
    _ = inputs.pit_membership.write_text(
        "code,name,market,instrument_type,effective_from,effective_to,available_at,source_hash\n"
        + f"005930,삼성전자,KOSPI,common_equity,20000101,20991231,20260103,{'b' * 64}\n",
        encoding="utf-8",
    )

    # When: the audit checks point-in-time availability.
    receipt = audit_market_authority(inputs)

    # Then: late evidence cannot cover the required decision membership.
    assert receipt.d1_universe.state == "BLOCKED"
    assert receipt.d1_universe.covered_membership_pairs == 0
    assert receipt.d1_universe.coverage_percent == 0.0


def test_authority_audit_rejects_unresolved_self_declared_source_hashes(
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path)
    with sqlite3.connect(inputs.daily_database) as connection:
        _ = connection.execute(
            'ALTER TABLE "A005930" ADD COLUMN "수정주가구분" INTEGER'
        )
    database_hash = hashlib.sha256(inputs.daily_database.read_bytes()).hexdigest()
    _ = inputs.price_provenance.write_text(
        json.dumps(
            {
                "schema_version": "kronos_price_provenance.v1",
                "database_sha256": database_hash,
                "source_system": "KIWOOM_OPENAPI_OPT10081",
                "source_field": "수정주가구분",
                "price_basis": "split_adjusted",
                "collection_option": "adjusted_price_enabled",
                "corporate_action_policy": "split_adjusted_dividend_excluded",
                "source_sha256": "a" * 64,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _ = inputs.current_official_metadata.write_text(
        "code,name,market,instrument_type,available_at,source_hash\n"
        + f"005930,삼성전자,KOSPI,common_equity,20260101,{'b' * 64}\n",
        encoding="utf-8",
    )
    _ = inputs.pit_membership.write_text(
        "code,name,market,instrument_type,effective_from,effective_to,available_at,source_hash\n"
        + f"005930,삼성전자,KOSPI,common_equity,20000101,20991231,20260101,{'b' * 64}\n",
        encoding="utf-8",
    )

    receipt = audit_market_authority(inputs)

    assert receipt.status == "BLOCKED_DATA_AUTHORITY"
    assert receipt.d0_price_basis.state == "BLOCKED"
    assert receipt.d1_universe.state == "BLOCKED"
    assert receipt.source_artifacts == ()
    assert receipt.d0_price_basis.checks[-1].check_id == (
        "PROVENANCE_SOURCE_REVIEW_VERIFIED"
    )
    assert receipt.d0_price_basis.checks[-1].passed is False
    assert receipt.d1_universe.checks[-1].passed is False


def test_authority_artifacts_publish_bounded_catalog_summary(tmp_path: Path) -> None:
    # Given: one completed fail-closed authority receipt.
    receipt = audit_market_authority(_inputs(tmp_path))

    # When: the receipt is published to a research-run directory.
    paths = write_authority_artifacts(receipt, tmp_path / "run")

    # Then: the catalog summary is compact while the full receipt remains separate.
    summary = AuthorityDashboardSummary.model_validate_json(paths.summary.read_bytes())
    assert summary.verdict == "BLOCKED_DATA_AUTHORITY"
    assert summary.algorithm == "DATA_AUTHORITY"
    assert summary.dataset_id == receipt.daily_database.sha256
    assert summary.historical_test_state == receipt.historical_test_state
    assert summary.reasons == (
        "D0_PRICE_BASIS_NOT_VERIFIED",
        "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED",
    )
    assert summary.promotion_allowed is False
    assert summary.fresh_oos_read is False
    assert summary.summary[0].policy == "D0 PRICE BASIS"
    assert summary.summary[1].required_membership_pairs == 1
    assert summary.summary[1].covered_membership_pairs == 0
    assert paths.receipt.read_text(encoding="utf-8").endswith("\n")
    with pytest.raises(
        DailyMarketAuthorityError,
        match="AUTHORITY_OUTPUT_ALREADY_EXISTS",
    ):
        _ = write_authority_artifacts(receipt, tmp_path / "run")


@pytest.mark.skipif(os.name != "nt", reason="Windows junction boundary")
def test_authority_artifacts_reject_junction_output(tmp_path: Path) -> None:
    # Given: an output path redirected through a Windows junction.
    outside = tmp_path / "outside"
    outside.mkdir()
    junction = tmp_path / "junction"
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("junction creation unavailable")
    try:
        input_root = tmp_path / "input"
        input_root.mkdir()
        receipt = audit_market_authority(_inputs(input_root))

        # When/Then: publication fails before any evidence escapes the run root.
        with pytest.raises(
            DailyMarketAuthorityError, match="AUTHORITY_OUTPUT_UNTRUSTED"
        ):
            _ = write_authority_artifacts(receipt, junction)
        assert tuple(outside.iterdir()) == ()
    finally:
        junction.rmdir()
