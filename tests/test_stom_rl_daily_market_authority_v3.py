from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from typing import Literal

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

import stom_rl.daily_market_authority_contract as authority_contract
from stom_rl.daily_market_authority_contract import (
    AuthorityCheck,
    AuthorityFileIdentity,
    AuthorityInputBinding,
    AuthorityInputRole,
    MarketAuthorityReceipt,
    PriceBasisAuthority,
    UniverseAuthority,
)
from stom_rl.daily_market_authority_review import verify_extraction_review
from stom_rl.daily_market_authority_review_contract import (
    SIGNING_DOMAIN,
    ExtractionReviewPolicy,
    ExtractionReviewStatement,
    NormalizedTargetReviewBinding,
    RawSourceReviewBinding,
    ReviewerScope,
    ReviewerTrustKey,
    ReviewerTrustStore,
    SignedExtractionReview,
    SignedExtractionReviewProof,
    canonical_bytes,
)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _identity(name: str, digest: str, size: int = 10) -> AuthorityFileIdentity:
    return AuthorityFileIdentity(
        path_suffix=name,
        size_bytes=size,
        modified_at_utc="2026-08-14T00:00:00+00:00",
        sha256=digest,
    )


def _key(
    principal: str,
    key_id: str,
    role: Literal["D0_REVIEWER", "D1_REVIEWER"],
    scopes: tuple[ReviewerScope, ...],
) -> tuple[Ed25519PrivateKey, ReviewerTrustKey]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private, ReviewerTrustKey(
        principal_uri=principal,
        key_id=key_id,
        role=role,
        scopes=scopes,
        algorithm="Ed25519",
        public_key_encoding="base64url-no-pad",
        public_key=_b64(public),
        not_before_utc="2026-01-01T00:00:00Z",
        not_after_utc="2027-01-01T00:00:00Z",
        status="ACTIVE",
    )


def _proof(
    private: Ed25519PrivateKey,
    key: ReviewerTrustKey,
    *,
    scope: ReviewerScope,
    target_role: Literal[
        "PRICE_PROVENANCE", "CURRENT_OFFICIAL_METADATA", "PIT_MEMBERSHIP"
    ],
    profile: Literal[
        "KIWOOM_OPT10081_PRICE_PROVENANCE_V1",
        "KRX_CURRENT_COMMON_EQUITY_V1",
        "KRX_PIT_COMMON_EQUITY_V1",
    ],
    target_hash: str,
    raw_hash: str,
    source_system: Literal["KIWOOM_OPENAPI", "KRX_DATA_PORTAL"],
    source_url: str,
    receipt_id: str,
    nonce_byte: bytes,
) -> SignedExtractionReviewProof:
    statement = ExtractionReviewStatement(
        schema="kronos_daily_market_extraction_review.v1",
        receipt_id=receipt_id,
        nonce=_b64(nonce_byte * 32),
        scope=scope,
        reviewer_principal=key.principal_uri,
        reviewer_key_id=key.key_id,
        reviewed_at_utc="2026-08-14T00:00:00Z",
        raw_sources=(
            RawSourceReviewBinding(
                source_system=source_system,
                source_url=source_url,
                sha256=raw_hash,
                size_bytes=10,
                available_at_utc="2026-08-13T00:00:00Z",
            ),
        ),
        normalized_target=NormalizedTargetReviewBinding(
            role=target_role,
            sha256=target_hash,
            size_bytes=10,
            normalization_profile=profile,
        ),
        policy=ExtractionReviewPolicy(
            policy_id="KRONOS_DAILY_MARKET_AUTHORITY_EXTRACTION",
            policy_version="1",
            evidence_kind="REAL",
            review_decision="APPROVE",
        ),
    )
    review = SignedExtractionReview(
        statement=statement,
        signature=_b64(private.sign(SIGNING_DOMAIN + canonical_bytes(statement))),
    )
    payload = canonical_bytes(review)
    return SignedExtractionReviewProof(
        receipt_sha256=hashlib.sha256(payload).hexdigest(),
        receipt_size_bytes=len(payload),
        review=review,
    )


def _verified_receipt(monkeypatch: pytest.MonkeyPatch) -> MarketAuthorityReceipt:
    d0_private, d0_key = _key(
        "reviewer://authority/d0",
        "11111111-1111-4111-8111-111111111111",
        "D0_REVIEWER",
        ("D0_PRICE_PROVENANCE",),
    )
    d1_private, d1_key = _key(
        "reviewer://authority/d1",
        "22222222-2222-4222-8222-222222222222",
        "D1_REVIEWER",
        ("D1_CURRENT_METADATA", "D1_PIT_MEMBERSHIP"),
    )
    store = ReviewerTrustStore(
        schema="kronos_daily_market_reviewer_trust.v1",
        keys=(d0_key, d1_key),
    )
    store_hash = hashlib.sha256(canonical_bytes(store)).hexdigest()
    monkeypatch.setattr(
        authority_contract, "PINNED_REVIEWER_TRUST_STORE_SHA256", store_hash
    )
    daily = _identity("daily.db", "1" * 64)
    stockinfo = _identity("stockinfo.json", "2" * 64)
    scores = _identity("scores.csv", "3" * 64)
    targets = (
        _identity("price.json", "4" * 64),
        _identity("current.csv", "5" * 64),
        _identity("pit.csv", "6" * 64),
    )
    raw = (
        _identity(f"{'7' * 64}.source", "7" * 64),
        _identity(f"{'8' * 64}.source", "8" * 64),
        _identity(f"{'9' * 64}.source", "9" * 64),
    )
    proofs = (
        _proof(
            d0_private,
            d0_key,
            scope="D0_PRICE_PROVENANCE",
            target_role="PRICE_PROVENANCE",
            profile="KIWOOM_OPT10081_PRICE_PROVENANCE_V1",
            target_hash="4" * 64,
            raw_hash="7" * 64,
            source_system="KIWOOM_OPENAPI",
            source_url="https://download.kiwoom.com/source",
            receipt_id="33333333-3333-4333-8333-333333333333",
            nonce_byte=b"a",
        ),
        _proof(
            d1_private,
            d1_key,
            scope="D1_CURRENT_METADATA",
            target_role="CURRENT_OFFICIAL_METADATA",
            profile="KRX_CURRENT_COMMON_EQUITY_V1",
            target_hash="5" * 64,
            raw_hash="8" * 64,
            source_system="KRX_DATA_PORTAL",
            source_url="https://data.krx.co.kr/source",
            receipt_id="44444444-4444-4444-8444-444444444444",
            nonce_byte=b"b",
        ),
        _proof(
            d1_private,
            d1_key,
            scope="D1_PIT_MEMBERSHIP",
            target_role="PIT_MEMBERSHIP",
            profile="KRX_PIT_COMMON_EQUITY_V1",
            target_hash="6" * 64,
            raw_hash="9" * 64,
            source_system="KRX_DATA_PORTAL",
            source_url="https://global.krx.co.kr/source",
            receipt_id="55555555-5555-4555-8555-555555555555",
            nonce_byte=b"c",
        ),
    )
    binding_values: tuple[tuple[AuthorityInputRole, AuthorityFileIdentity], ...] = (
        ("DAILY_DATABASE", daily),
        ("STOCKINFO_DATABASE", stockinfo),
        ("CANDIDATE_SCORES", scores),
        ("PRICE_PROVENANCE", targets[0]),
        ("CURRENT_OFFICIAL_METADATA", targets[1]),
        ("PIT_MEMBERSHIP", targets[2]),
    )
    bindings = tuple(
        AuthorityInputBinding(role=role, state="PRESENT", identity=identity)
        for role, identity in binding_values
    )
    return MarketAuthorityReceipt(
        schema_version="kronos_daily_market_authority.v3",
        research_id="DAILY_MARKET_AUTHORITY_2026_08_14_003",
        status="VERIFIED_RESEARCH_DATA_AUTHORITY",
        daily_database=daily,
        input_bindings=bindings,
        source_artifacts=raw,
        d0_price_basis=PriceBasisAuthority(
            state="VERIFIED",
            price_basis="split_adjusted",
            provenance_state="PRESENT",
            local_columns=("수정주가구분",),
            checks=tuple(
                AuthorityCheck(check_id=name, passed=True, observed="verified")
                for name in (
                    "ALL_DAILY_TABLES_EXPLICIT_PRICE_BASIS",
                    "INDEPENDENT_PROVENANCE_PRESENT",
                    "PROVENANCE_BINDS_DATABASE_SHA256",
                    "PROVENANCE_SOURCE_REVIEW_VERIFIED",
                )
            ),
        ),
        d1_universe=UniverseAuthority(
            state="VERIFIED",
            current_metadata_state="PRESENT",
            pit_membership_state="PRESENT",
            daily_table_count=1,
            required_membership_pairs=1,
            covered_membership_pairs=1,
            coverage_percent=100.0,
            checks=tuple(
                AuthorityCheck(check_id=name, passed=True, observed="verified")
                for name in (
                    "STOCKINFO_METADATA_PRESENT",
                    "CURRENT_OFFICIAL_METADATA_PRESENT",
                    "PIT_MEMBERSHIP_COMPLETE_AND_AVAILABLE",
                    "KRX_SOURCE_REVIEWS_VERIFIED",
                )
            ),
        ),
        blockers=(),
        source_urls=(
            "https://download.kiwoom.com/source",
            "https://data.krx.co.kr/source",
        ),
        verified_at_utc="2026-08-14T01:00:00Z",
        reviewer_trust_store_sha256=store_hash,
        reviewer_trust_store=store,
        signed_extraction_reviews=proofs,
        historical_test_state="FEATURES_PARSED_REWARDS_PRICES_ACTION_EVALUATION_NOT_READ_CONTAMINATED",
        fresh_oos_read=False,
        promotion_allowed=False,
        live_ready=False,
    )


def test_verified_v3_requires_complete_signed_and_derived_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _verified_receipt(monkeypatch)

    assert receipt.status == "VERIFIED_RESEARCH_DATA_AUTHORITY"
    for field, value in (("coverage_percent", 99.0), ("covered_membership_pairs", 0)):
        forged = receipt.model_dump(mode="json")
        forged["d1_universe"][field] = value
        with pytest.raises(ValidationError, match="verified D1 checks"):
            _ = MarketAuthorityReceipt.model_validate(forged)
    forged = receipt.model_dump(mode="json")
    forged["d0_price_basis"]["checks"][0]["passed"] = False
    with pytest.raises(ValidationError, match="verified D0 checks"):
        _ = MarketAuthorityReceipt.model_validate(forged)
    forged = receipt.model_dump(mode="json")
    forged["signed_extraction_reviews"] = forged["signed_extraction_reviews"][:-1]
    with pytest.raises(ValidationError, match="three unique reviews"):
        _ = MarketAuthorityReceipt.model_validate(forged)


def test_verified_v3_subproofs_revalidate_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _verified_receipt(monkeypatch)
    verification_time = datetime(2026, 8, 14, 1, tzinfo=timezone.utc)

    for proof in receipt.signed_extraction_reviews:
        statement = proof.review.statement
        _ = verify_extraction_review(
            receipt.reviewer_trust_store,
            proof.review,
            expected_scope=statement.scope,
            target_sha256=statement.normalized_target.sha256,
            target_size_bytes=statement.normalized_target.size_bytes,
            raw_sources=tuple(
                (source.sha256, source.size_bytes) for source in statement.raw_sources
            ),
            verification_time=verification_time,
        )
