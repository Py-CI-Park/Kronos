from __future__ import annotations

import base64
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from stom_rl.daily_market_authority_review import (
    parse_pinned_trust_store,
    verify_extraction_review,
)
from stom_rl.daily_market_authority_review_contract import (
    SIGNING_DOMAIN,
    ExtractionReviewPolicy,
    ExtractionReviewStatement,
    NormalizedTargetReviewBinding,
    RawSourceReviewBinding,
    ReviewerTrustKey,
    ReviewerTrustStore,
    SignedExtractionReview,
    canonical_bytes,
)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _fixture() -> tuple[
    Ed25519PrivateKey,
    ReviewerTrustStore,
    ExtractionReviewStatement,
]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key = ReviewerTrustKey(
        principal_uri="reviewer://market-authority/d0",
        key_id="11111111-1111-4111-8111-111111111111",
        role="D0_REVIEWER",
        scopes=("D0_PRICE_PROVENANCE",),
        algorithm="Ed25519",
        public_key_encoding="base64url-no-pad",
        public_key=_b64(public_key),
        not_before_utc="2026-01-01T00:00:00Z",
        not_after_utc="2027-01-01T00:00:00Z",
        status="ACTIVE",
    )
    statement = ExtractionReviewStatement(
        schema="kronos_daily_market_extraction_review.v1",
        receipt_id="22222222-2222-4222-8222-222222222222",
        nonce=_b64(b"n" * 32),
        scope="D0_PRICE_PROVENANCE",
        reviewer_principal=key.principal_uri,
        reviewer_key_id=key.key_id,
        reviewed_at_utc="2026-08-14T00:00:00Z",
        raw_sources=(
            RawSourceReviewBinding(
                source_system="KIWOOM_OPENAPI",
                source_url="https://download.kiwoom.com/source",
                sha256="a" * 64,
                size_bytes=17,
                available_at_utc="2026-08-13T00:00:00Z",
            ),
        ),
        normalized_target=NormalizedTargetReviewBinding(
            role="PRICE_PROVENANCE",
            sha256="b" * 64,
            size_bytes=31,
            normalization_profile="KIWOOM_OPT10081_PRICE_PROVENANCE_V1",
        ),
        policy=ExtractionReviewPolicy(
            policy_id="KRONOS_DAILY_MARKET_AUTHORITY_EXTRACTION",
            policy_version="1",
            evidence_kind="REAL",
            review_decision="APPROVE",
        ),
    )
    return (
        private_key,
        ReviewerTrustStore(schema="kronos_daily_market_reviewer_trust.v1", keys=(key,)),
        statement,
    )


def _signed(
    private_key: Ed25519PrivateKey,
    statement: ExtractionReviewStatement,
    *,
    domain: bytes = SIGNING_DOMAIN,
) -> SignedExtractionReview:
    return SignedExtractionReview(
        statement=statement,
        signature=_b64(private_key.sign(domain + canonical_bytes(statement))),
    )


def _verify(store: ReviewerTrustStore, review: SignedExtractionReview) -> None:
    _ = verify_extraction_review(
        store,
        review,
        expected_scope="D0_PRICE_PROVENANCE",
        target_sha256="b" * 64,
        target_size_bytes=31,
        raw_sources=(("a" * 64, 17),),
        verification_time=datetime(2026, 8, 14, 1, tzinfo=timezone.utc),
    )


def test_signed_extraction_review_accepts_exact_test_only_ed25519_binding() -> None:
    private_key, store, statement = _fixture()

    _verify(store, _signed(private_key, statement))


def test_signed_extraction_review_rejects_wrong_domain_and_signature() -> None:
    private_key, store, statement = _fixture()

    with pytest.raises(ValueError, match="signature invalid"):
        _verify(store, _signed(private_key, statement, domain=b"WRONG\x00"))
    tampered = _signed(private_key, statement).model_copy(
        update={"signature": _b64(b"x" * 64)}
    )
    with pytest.raises(ValueError, match="signature invalid"):
        _verify(store, tampered)


def test_signed_extraction_review_rejects_target_and_raw_substitution() -> None:
    private_key, store, statement = _fixture()
    review = _signed(private_key, statement)

    with pytest.raises(ValueError, match="target mismatch"):
        _ = verify_extraction_review(
            store,
            review,
            expected_scope="D0_PRICE_PROVENANCE",
            target_sha256="c" * 64,
            target_size_bytes=31,
            raw_sources=(("a" * 64, 17),),
            verification_time=datetime(2026, 8, 14, 1, tzinfo=timezone.utc),
        )
    with pytest.raises(ValueError, match="raw-source binding mismatch"):
        _ = verify_extraction_review(
            store,
            review,
            expected_scope="D0_PRICE_PROVENANCE",
            target_sha256="b" * 64,
            target_size_bytes=31,
            raw_sources=(("d" * 64, 17),),
            verification_time=datetime(2026, 8, 14, 1, tzinfo=timezone.utc),
        )


def test_signed_extraction_review_rejects_nonofficial_source_url() -> None:
    private_key, store, statement = _fixture()
    raw = statement.raw_sources[0].model_copy(
        update={"source_url": "https://example.com/forged"}
    )
    changed = statement.model_copy(update={"raw_sources": (raw,)})

    with pytest.raises(ValueError, match="source URL is not official"):
        _verify(store, _signed(private_key, changed))


def test_production_trust_store_is_canonical_empty_and_pinned() -> None:
    raw = b'{"keys":[],"schema":"kronos_daily_market_reviewer_trust.v1"}'

    assert parse_pinned_trust_store(raw).keys == ()
    with pytest.raises(ValueError, match="pin mismatch"):
        _ = parse_pinned_trust_store(raw + b"\n")
