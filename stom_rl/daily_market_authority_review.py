"""Pinned Ed25519 verification for daily-market extraction reviews."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .daily_market_authority_review_contract import (
    SIGNING_DOMAIN,
    ReviewerScope,
    ReviewerTrustKey,
    ReviewerTrustStore,
    SignedExtractionReview,
    canonical_bytes,
    decode_base64url,
    parse_utc_seconds,
)

PINNED_REVIEWER_TRUST_STORE_SHA256 = (
    "009c959493337799750dcfbca842e445f35308f83a178054b476d633faac072c"
)
_SCOPE_CONTRACT = {
    "D0_PRICE_PROVENANCE": (
        "D0_REVIEWER",
        "PRICE_PROVENANCE",
        "KIWOOM_OPT10081_PRICE_PROVENANCE_V1",
        "KIWOOM_OPENAPI",
    ),
    "D1_CURRENT_METADATA": (
        "D1_REVIEWER",
        "CURRENT_OFFICIAL_METADATA",
        "KRX_CURRENT_COMMON_EQUITY_V1",
        "KRX_DATA_PORTAL",
    ),
    "D1_PIT_MEMBERSHIP": (
        "D1_REVIEWER",
        "PIT_MEMBERSHIP",
        "KRX_PIT_COMMON_EQUITY_V1",
        "KRX_DATA_PORTAL",
    ),
}
_OFFICIAL_SOURCE_HOSTS = {
    "KIWOOM_OPENAPI": frozenset({"download.kiwoom.com"}),
    "KRX_DATA_PORTAL": frozenset({"data.krx.co.kr", "global.krx.co.kr"}),
}


def parse_pinned_trust_store(raw: bytes) -> ReviewerTrustStore:
    """Parse only the exact repository-pinned canonical public trust store."""
    if hashlib.sha256(raw).hexdigest() != PINNED_REVIEWER_TRUST_STORE_SHA256:
        raise ValueError("reviewer trust store pin mismatch")
    store = ReviewerTrustStore.model_validate_json(raw)
    if raw != canonical_bytes(store):
        raise ValueError("reviewer trust store is not canonical JCS")
    return store


def verify_extraction_review(
    store: ReviewerTrustStore,
    review: SignedExtractionReview,
    *,
    expected_scope: ReviewerScope,
    target_sha256: str,
    target_size_bytes: int,
    raw_sources: tuple[tuple[str, int], ...],
    verification_time: datetime,
) -> ReviewerTrustKey:
    """Verify reviewer authority and exact raw-to-normalized bindings."""
    statement = review.statement
    role, target_role, profile, source_system = _SCOPE_CONTRACT[expected_scope]
    if statement.scope != expected_scope:
        raise ValueError("signed review scope mismatch")
    target = statement.normalized_target
    if (
        target.role,
        target.normalization_profile,
        target.sha256,
        target.size_bytes,
    ) != (target_role, profile, target_sha256, target_size_bytes):
        raise ValueError("signed review target mismatch")
    observed_raw = tuple(sorted(raw_sources))
    signed_raw = tuple(
        (source.sha256, source.size_bytes) for source in statement.raw_sources
    )
    if signed_raw != observed_raw or any(
        source.source_system != source_system for source in statement.raw_sources
    ):
        raise ValueError("signed review raw-source binding mismatch")
    if any(
        urlsplit(source.source_url).hostname
        not in _OFFICIAL_SOURCE_HOSTS[source_system]
        for source in statement.raw_sources
    ):
        raise ValueError("signed review source URL is not official")
    key = next(
        (
            candidate
            for candidate in store.keys
            if candidate.key_id == statement.reviewer_key_id
            and candidate.principal_uri == statement.reviewer_principal
        ),
        None,
    )
    if (
        key is None
        or key.status != "ACTIVE"
        or key.role != role
        or expected_scope not in key.scopes
    ):
        raise ValueError("reviewer key is not trusted for scope")
    reviewed_at = parse_utc_seconds(statement.reviewed_at_utc)
    if not (
        parse_utc_seconds(key.not_before_utc)
        <= reviewed_at
        <= parse_utc_seconds(key.not_after_utc)
    ):
        raise ValueError("review time outside key validity")
    if verification_time.tzinfo != timezone.utc or reviewed_at > verification_time:
        raise ValueError("review time is in the future")
    try:
        Ed25519PublicKey.from_public_bytes(decode_base64url(key.public_key, 32)).verify(
            decode_base64url(review.signature, 64),
            SIGNING_DOMAIN + canonical_bytes(statement),
        )
    except InvalidSignature as error:
        raise ValueError("signed extraction review signature invalid") from error
    return key


__all__ = [
    "PINNED_REVIEWER_TRUST_STORE_SHA256",
    "parse_pinned_trust_store",
    "verify_extraction_review",
]
