from stom_rl.daily_market_authority_local_verdict import (
    d0_authority_verified,
    d1_authority_verified,
)


def test_d0_shared_verifier_rejects_empty_or_incomplete_daily_tables() -> None:
    complete = dict(
        provenance_present=True,
        provenance_matches_database=True,
        raw_sources_resolved=True,
        signed_review_verified=True,
    )

    assert not d0_authority_verified(
        table_count=0,
        explicit_basis_table_count=0,
        **complete,
    )
    assert not d0_authority_verified(
        table_count=2,
        explicit_basis_table_count=1,
        **complete,
    )
    assert d0_authority_verified(
        table_count=2,
        explicit_basis_table_count=2,
        **complete,
    )


def test_d1_shared_verifier_requires_nonempty_complete_pit_and_stockinfo() -> None:
    complete = dict(
        current_metadata_present=True,
        pit_membership_present=True,
        raw_sources_resolved=True,
        current_review_verified=True,
        pit_review_verified=True,
    )

    assert not d1_authority_verified(
        required_membership_pairs=0,
        covered_membership_pairs=0,
        stockinfo_rows=1,
        **complete,
    )
    assert not d1_authority_verified(
        required_membership_pairs=2,
        covered_membership_pairs=1,
        stockinfo_rows=1,
        **complete,
    )
    assert not d1_authority_verified(
        required_membership_pairs=2,
        covered_membership_pairs=2,
        stockinfo_rows=0,
        **complete,
    )
    assert d1_authority_verified(
        required_membership_pairs=2,
        covered_membership_pairs=2,
        stockinfo_rows=1,
        **complete,
    )
