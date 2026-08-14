"""Custody-safe loading of signed daily-market extraction reviews."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from .daily_market_authority_contract import (
    AuthorityFileIdentity,
    DailyMarketAuthorityError,
)
from .daily_market_authority_file_custody import read_stable_file_bytes
from .daily_market_authority_review import (
    parse_pinned_trust_store,
    verify_extraction_review,
)
from .daily_market_authority_review_contract import (
    ReviewerScope,
    ReviewerTrustStore,
    SignedExtractionReview,
    SignedExtractionReviewProof,
    canonical_bytes,
)
from .daily_market_path_custody import has_reparse_component

_ROLE_NAME: dict[ReviewerScope, str] = {
    "D0_PRICE_PROVENANCE": "price_provenance",
    "D1_CURRENT_METADATA": "current_official_metadata",
    "D1_PIT_MEMBERSHIP": "pit_membership",
}


def load_pinned_reviewer_trust_store(path: Path) -> ReviewerTrustStore:
    """Load only the repository-pinned canonical public trust store."""
    raw, _identity = read_stable_file_bytes(path, max_bytes=65_536)
    try:
        return parse_pinned_trust_store(raw)
    except (ValueError, ValidationError) as error:
        raise DailyMarketAuthorityError("REVIEWER_TRUST_STORE_INVALID") from error


def review_receipt_name(scope: ReviewerScope, target_sha256: str) -> str:
    """Derive a receipt name; signed evidence never chooses a local path."""
    return f"{_ROLE_NAME[scope]}.{target_sha256}.review.json"


def load_verified_extraction_review(
    root: Path,
    store: ReviewerTrustStore,
    *,
    scope: ReviewerScope,
    target: AuthorityFileIdentity | None,
    raw_sources: tuple[AuthorityFileIdentity, ...],
    verification_time: datetime,
) -> SignedExtractionReviewProof | None:
    """Return a verified proof or fail closed with no proof."""
    if (
        target is None
        or not raw_sources
        or has_reparse_component(root)
        or not root.is_dir()
    ):
        return None
    receipt_path = root / review_receipt_name(scope, target.sha256)
    if has_reparse_component(receipt_path) or not receipt_path.is_file():
        return None
    try:
        raw, identity = read_stable_file_bytes(receipt_path, max_bytes=65_536)
        review = SignedExtractionReview.model_validate_json(raw)
        if raw != canonical_bytes(review):
            return None
        _ = verify_extraction_review(
            store,
            review,
            expected_scope=scope,
            target_sha256=target.sha256,
            target_size_bytes=target.size_bytes,
            raw_sources=tuple(
                sorted((source.sha256, source.size_bytes) for source in raw_sources)
            ),
            verification_time=verification_time,
        )
        if hashlib.sha256(raw).hexdigest() != identity.sha256:
            return None
        return SignedExtractionReviewProof(
            receipt_sha256=identity.sha256,
            receipt_size_bytes=identity.size_bytes,
            review=review,
        )
    except (OSError, DailyMarketAuthorityError, ValidationError, ValueError):
        return None


__all__ = [
    "load_pinned_reviewer_trust_store",
    "load_verified_extraction_review",
    "review_receipt_name",
]
