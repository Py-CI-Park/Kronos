"""Read-only D0/D1 authority audit for the daily-market RL lane."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .daily_market_authority_bound_sources import (
    bound_candidate_pairs,
    bound_current_metadata,
    bound_pit_records,
    bound_price_provenance,
)
from .daily_market_authority_contract import (
    AuthorityCheck,
    AuthorityInputBinding,
    MarketAuthorityReceipt,
    PriceBasisAuthority,
    UniverseAuthority,
)
from .daily_market_authority_snapshot import (
    AuthorityDatabaseSnapshots,
    immutable_authority_database_snapshots,
)
from .daily_market_authority_sources import (
    covered_pairs,
    daily_column_presence_count,
    ensure_required_file,
    local_columns,
    resolve_reviewed_source_artifacts,
)
from .daily_market_stockinfo_authority import (
    StockinfoAuthorityEvidence,
    observe_stockinfo_authority,
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
    source_artifact_root: Path


def audit_market_authority(inputs: MarketAuthorityInputs) -> MarketAuthorityReceipt:
    """Build a fail-closed receipt from local and independent authority evidence."""
    daily_source = ensure_required_file(
        inputs.daily_database,
        "DAILY_DATABASE_UNTRUSTED",
    )
    stockinfo_source = ensure_required_file(
        inputs.stockinfo_database, "STOCKINFO_DATABASE_UNTRUSTED"
    )
    score_path = ensure_required_file(
        inputs.candidate_scores, "CANDIDATE_SCORES_UNTRUSTED"
    )
    stockinfo = observe_stockinfo_authority(stockinfo_source)
    with immutable_authority_database_snapshots(daily_source) as snapshots:
        return _audit_database_snapshots(inputs, score_path, snapshots, stockinfo)


def _audit_database_snapshots(
    inputs: MarketAuthorityInputs,
    score_path: Path,
    snapshots: AuthorityDatabaseSnapshots,
    stockinfo: StockinfoAuthorityEvidence,
) -> MarketAuthorityReceipt:
    daily_path = snapshots.daily_path
    identity = snapshots.daily_identity
    tables = tuple(list_daily_tables(daily_path))
    columns = local_columns(daily_path, tables)
    explicit_basis_table_count = daily_column_presence_count(
        daily_path,
        tables,
        "수정주가구분",
    )
    provenance_state, provenance, provenance_binding = bound_price_provenance(
        inputs.price_provenance
    )
    provenance_matches = (
        provenance is not None and provenance.database_sha256 == identity.sha256
    )
    declared_source_hashes = frozenset(
        {provenance.source_sha256} if provenance is not None else set()
    )
    d0_source_resolved, d0_source_artifacts = resolve_reviewed_source_artifacts(
        inputs.source_artifact_root,
        declared_source_hashes,
    )
    local_basis_explicit = bool(tables) and explicit_basis_table_count == len(tables)
    d0_verified = (
        provenance_state == "PRESENT"
        and provenance_matches
        and local_basis_explicit
        and d0_source_resolved
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
                check_id="ALL_DAILY_TABLES_EXPLICIT_PRICE_BASIS",
                passed=local_basis_explicit,
                observed=f"covered={explicit_basis_table_count}/{len(tables)}",
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
            AuthorityCheck(
                check_id="PROVENANCE_SOURCE_REVIEW_VERIFIED",
                passed=d0_source_resolved,
                observed=(
                    f"content_bound={len(d0_source_artifacts)}/{len(declared_source_hashes)};signed_review=missing"
                ),
            ),
        ),
    )
    required, score_binding = bound_candidate_pairs(score_path)
    current_state, current_source_hashes, current_binding = bound_current_metadata(
        inputs.current_official_metadata
    )
    pit_state, pit_rows, pit_binding = bound_pit_records(inputs.pit_membership)
    d1_declared_hashes = frozenset(
        (*current_source_hashes, *(row.source_hash for row in pit_rows))
    )
    d1_sources_resolved, d1_source_artifacts = resolve_reviewed_source_artifacts(
        inputs.source_artifact_root,
        d1_declared_hashes,
    )
    covered = covered_pairs(required, pit_rows)
    coverage = (covered / len(required)) * 100.0
    stockinfo_rows = stockinfo.row_count
    d1_verified = (
        current_state == "PRESENT"
        and pit_state == "PRESENT"
        and covered == len(required)
        and stockinfo_rows > 0
        and d1_sources_resolved
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
            AuthorityCheck(
                check_id="KRX_SOURCE_REVIEWS_VERIFIED",
                passed=d1_sources_resolved,
                observed=(
                    f"content_bound={len(d1_source_artifacts)}/{len(d1_declared_hashes)};signed_review=missing"
                ),
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
        schema_version="kronos_daily_market_authority.v2",
        research_id="DAILY_MARKET_AUTHORITY_2026_08_10_002",
        status="VERIFIED_RESEARCH_DATA_AUTHORITY"
        if not blockers
        else "BLOCKED_DATA_AUTHORITY",
        daily_database=identity,
        input_bindings=(
            AuthorityInputBinding(
                role="DAILY_DATABASE",
                state="PRESENT",
                identity=identity,
            ),
            AuthorityInputBinding(
                role="STOCKINFO_DATABASE",
                state="PRESENT",
                identity=stockinfo.identity,
            ),
            score_binding,
            provenance_binding,
            current_binding,
            pit_binding,
        ),
        source_artifacts=tuple(
            {
                identity.sha256: identity
                for identity in (*d0_source_artifacts, *d1_source_artifacts)
            }.values()
        ),
        d0_price_basis=d0,
        d1_universe=d1,
        blockers=blockers,
        source_urls=(KIWOOM_GUIDE_URL, KRX_MARKET_URL, KRX_LISTED_URL),
        historical_test_state=(
            "FEATURES_PARSED_REWARDS_PRICES_ACTION_EVALUATION_NOT_READ_CONTAMINATED"
        ),
        fresh_oos_read=False,
        promotion_allowed=False,
        live_ready=False,
    )


__all__ = ["MarketAuthorityInputs", "audit_market_authority"]
