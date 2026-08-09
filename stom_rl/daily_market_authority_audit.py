"""Read-only D0/D1 authority audit for the daily-market RL lane."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .daily_market_authority_contract import (
    AuthorityCheck,
    MarketAuthorityReceipt,
    PriceBasisAuthority,
    UniverseAuthority,
)
from .daily_market_authority_sources import (
    candidate_pairs,
    covered_pairs,
    current_metadata_state,
    ensure_required_file,
    file_identity,
    local_columns,
    pit_records,
    price_provenance,
    stockinfo_count,
)
from .daily_ohlcv_db import list_daily_tables

KIWOOM_GUIDE_URL: Final = (
    "https://download.kiwoom.com/web/openapi/kiwoom_openapi_plus_devguide_ver_1.1.pdf"
)
KRX_MARKET_URL: Final = (
    "https://data.krx.co.kr/contents/MDC/MDI/outerLoader/index.cmd?screenId=MDCSTAT015"
)
KRX_LISTED_URL: Final = (
    "https://global.krx.co.kr/contents/GLB/03/0308/0308010000/GLB0308010000.jsp"
)


@dataclass(frozen=True, slots=True)
class MarketAuthorityInputs:
    """Explicit source paths; none of them may be mutated by the audit."""

    daily_database: Path
    stockinfo_database: Path
    candidate_scores: Path
    price_provenance: Path
    current_official_metadata: Path
    pit_membership: Path


def audit_market_authority(inputs: MarketAuthorityInputs) -> MarketAuthorityReceipt:
    """Build a fail-closed receipt from local and independent authority evidence."""
    daily_path = ensure_required_file(inputs.daily_database, "DAILY_DATABASE_UNTRUSTED")
    stockinfo_path = ensure_required_file(
        inputs.stockinfo_database, "STOCKINFO_DATABASE_UNTRUSTED"
    )
    score_path = ensure_required_file(
        inputs.candidate_scores, "CANDIDATE_SCORES_UNTRUSTED"
    )
    identity = file_identity(daily_path)
    tables = tuple(list_daily_tables(daily_path))
    columns = local_columns(daily_path, tables)
    provenance_state, provenance = price_provenance(inputs.price_provenance)
    provenance_matches = (
        provenance is not None and provenance.database_sha256 == identity.sha256
    )
    local_basis_explicit = "수정주가구분" in columns
    d0_verified = (
        provenance_state == "PRESENT" and provenance_matches and local_basis_explicit
    )
    d0 = PriceBasisAuthority(
        state="VERIFIED" if d0_verified else "BLOCKED",
        price_basis=provenance.price_basis
        if d0_verified and provenance is not None
        else "unknown",
        provenance_state=provenance_state,
        local_columns=columns,
        checks=(
            AuthorityCheck(
                check_id="LOCAL_SCHEMA_EXPLICIT_PRICE_BASIS",
                passed=local_basis_explicit,
                observed="present" if local_basis_explicit else "missing",
            ),
            AuthorityCheck(
                check_id="INDEPENDENT_PROVENANCE_PRESENT",
                passed=provenance_state == "PRESENT",
                observed=provenance_state,
            ),
            AuthorityCheck(
                check_id="PROVENANCE_BINDS_DATABASE_SHA256",
                passed=provenance_matches,
                observed="matched" if provenance_matches else "missing_or_mismatch",
            ),
        ),
    )
    required = candidate_pairs(score_path)
    current_state = current_metadata_state(inputs.current_official_metadata)
    pit_state, pit_rows = pit_records(inputs.pit_membership)
    covered = covered_pairs(required, pit_rows)
    coverage = (covered / len(required)) * 100.0
    stockinfo_rows = stockinfo_count(stockinfo_path)
    d1_verified = (
        current_state == "PRESENT"
        and pit_state == "PRESENT"
        and covered == len(required)
    )
    d1 = UniverseAuthority(
        state="VERIFIED" if d1_verified else "BLOCKED",
        current_metadata_state=current_state,
        pit_membership_state=pit_state,
        daily_table_count=len(tables),
        required_membership_pairs=len(required),
        covered_membership_pairs=covered,
        coverage_percent=coverage,
        checks=(
            AuthorityCheck(
                check_id="STOCKINFO_METADATA_PRESENT",
                passed=stockinfo_rows > 0,
                observed=f"rows={stockinfo_rows}",
            ),
            AuthorityCheck(
                check_id="CURRENT_OFFICIAL_METADATA_PRESENT",
                passed=current_state == "PRESENT",
                observed=current_state,
            ),
            AuthorityCheck(
                check_id="PIT_MEMBERSHIP_COMPLETE_AND_AVAILABLE",
                passed=covered == len(required) and pit_state == "PRESENT",
                observed=f"covered={covered}/{len(required)}",
            ),
        ),
    )
    blockers = tuple(
        blocker
        for blocker, passed in (
            ("D0_PRICE_BASIS_NOT_VERIFIED", d0_verified),
            ("D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED", d1_verified),
        )
        if not passed
    )
    return MarketAuthorityReceipt(
        schema_version="kronos_daily_market_authority.v1",
        research_id="DAILY_MARKET_AUTHORITY_2026_08_10_001",
        status="VERIFIED_RESEARCH_DATA_AUTHORITY"
        if not blockers
        else "BLOCKED_DATA_AUTHORITY",
        daily_database=identity,
        d0_price_basis=d0,
        d1_universe=d1,
        blockers=blockers,
        source_urls=(KIWOOM_GUIDE_URL, KRX_MARKET_URL, KRX_LISTED_URL),
        historical_test_read=False,
        fresh_oos_read=False,
        promotion_allowed=False,
        live_ready=False,
    )


__all__ = ["MarketAuthorityInputs", "audit_market_authority"]
