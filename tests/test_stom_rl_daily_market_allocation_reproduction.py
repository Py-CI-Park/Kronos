"""Exact reference comparison tests for post-hoc allocation reproduction."""

from __future__ import annotations

import hashlib

from stom_rl.daily_market_allocation_reproduction import (
    allocation_reproduction_projection,
    compare_allocation_reproduction,
)
from tests.daily_market_allocation_fixtures import canonical_allocation_receipt


def test_reproduction_matches_the_hash_bound_001_evidence() -> None:
    reference = canonical_allocation_receipt({})
    reference_payload = reference.model_dump_json().encode()

    evidence = compare_allocation_reproduction(
        reference,
        allocation_reproduction_projection(reference),
        reference_receipt_sha256=hashlib.sha256(reference_payload).hexdigest(),
    )

    assert evidence.reference_research_id.endswith("_001")
    assert evidence.exact_match is True
    assert evidence.reference_evidence_sha256 == evidence.observed_evidence_sha256


def test_reproduction_records_a_mismatch_instead_of_claiming_success() -> None:
    reference = canonical_allocation_receipt({})
    changed = reference.model_copy(
        update={
            "behavior_transition_count": reference.behavior_transition_count + 1,
        }
    )

    evidence = compare_allocation_reproduction(
        reference,
        allocation_reproduction_projection(changed),
        reference_receipt_sha256="a" * 64,
    )

    assert evidence.exact_match is False
    assert evidence.reference_evidence_sha256 != evidence.observed_evidence_sha256
