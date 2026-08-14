"""Shared deterministic D0/D1 predicates for authority producers and consumers."""

from __future__ import annotations


def d0_authority_verified(
    *,
    table_count: int,
    explicit_basis_table_count: int,
    provenance_present: bool,
    provenance_matches_database: bool,
    raw_sources_resolved: bool,
    signed_review_verified: bool,
) -> bool:
    """Require nonempty daily data and every D0 custody/review condition."""
    return (
        table_count > 0
        and explicit_basis_table_count == table_count
        and provenance_present
        and provenance_matches_database
        and raw_sources_resolved
        and signed_review_verified
    )


def d1_authority_verified(
    *,
    current_metadata_present: bool,
    pit_membership_present: bool,
    required_membership_pairs: int,
    covered_membership_pairs: int,
    stockinfo_rows: int,
    raw_sources_resolved: bool,
    current_review_verified: bool,
    pit_review_verified: bool,
) -> bool:
    """Require nonempty complete PIT coverage and both signed D1 reviews."""
    return (
        current_metadata_present
        and pit_membership_present
        and required_membership_pairs > 0
        and covered_membership_pairs == required_membership_pairs
        and stockinfo_rows > 0
        and raw_sources_resolved
        and current_review_verified
        and pit_review_verified
    )


__all__ = ["d0_authority_verified", "d1_authority_verified"]
