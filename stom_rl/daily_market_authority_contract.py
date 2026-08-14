"""Typed D0/D1 source-authority evidence for the daily-market RL lane."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import override

from .daily_market_authority_review import (
    PINNED_REVIEWER_TRUST_STORE_SHA256,
    verify_extraction_review,
)
from .daily_market_authority_review_contract import (
    ReviewerScope,
    ReviewerTrustStore,
    SignedExtractionReviewProof,
    canonical_bytes,
)


def _empty_reviewer_trust_store() -> ReviewerTrustStore:
    return ReviewerTrustStore(
        schema="kronos_daily_market_reviewer_trust.v1",
        keys=(),
    )


class DailyMarketAuthorityError(Exception):
    """A typed boundary failure; traceback assignment requires mutation."""

    __slots__: ClassVar[tuple[str, str]] = ("code", "detail")

    code: str
    detail: str

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code, detail)
        self.code = code
        self.detail = detail

    @override
    def __str__(self) -> str:
        return self.code if not self.detail else f"{self.code}:{self.detail}"


class AuthorityCheck(BaseModel):
    """One directly observed authority condition."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    passed: bool
    observed: str


class AuthorityFileIdentity(BaseModel):
    """Content identity for an immutable research input."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    identity_kind: Literal[
        "WHOLE_FILE_SHA256",
        "CANONICAL_SQLITE_QUERY_SHA256",
    ] = "WHOLE_FILE_SHA256"
    path_suffix: str
    size_bytes: int = Field(gt=0)
    modified_at_utc: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


AuthorityInputRole = Literal[
    "DAILY_DATABASE",
    "STOCKINFO_DATABASE",
    "CANDIDATE_SCORES",
    "PRICE_PROVENANCE",
    "CURRENT_OFFICIAL_METADATA",
    "PIT_MEMBERSHIP",
]


class AuthorityInputBinding(BaseModel):
    """Exact file identity or fail-closed absence for every audited input."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    role: AuthorityInputRole
    state: Literal["PRESENT", "MISSING", "INVALID"]
    identity: AuthorityFileIdentity | None

    @model_validator(mode="after")
    def _identity_matches_state(self) -> Self:
        if (self.state == "PRESENT") != (self.identity is not None):
            raise ValueError("authority input identity/state mismatch")
        return self


class PriceProvenanceRecord(BaseModel):
    """Independent declaration binding collection semantics to the DB content."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_price_provenance.v1"]
    database_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_system: Literal["KIWOOM_OPENAPI_OPT10081"]
    source_field: Literal["수정주가구분"]
    price_basis: Literal["raw", "adjusted", "split_adjusted", "total_return_adjusted"]
    collection_option: str = Field(min_length=1)
    corporate_action_policy: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PitMembershipRecord(BaseModel):
    """One dated, available-at universe membership observation."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(pattern=r"^[0-9]{6}$")
    name: str = Field(min_length=1)
    market: Literal["KOSPI", "KOSDAQ", "KONEX"]
    instrument_type: Literal["common_equity"]
    effective_from: str = Field(pattern=r"^[0-9]{8}$")
    effective_to: str = Field(pattern=r"^[0-9]{8}$")
    available_at: str = Field(pattern=r"^[0-9]{8}$")
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class PriceBasisAuthority(BaseModel):
    """D0 price-basis verdict and its observed checks."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    state: Literal["VERIFIED", "BLOCKED"]
    price_basis: Literal[
        "raw", "adjusted", "split_adjusted", "total_return_adjusted", "unknown"
    ]
    provenance_state: Literal["PRESENT", "MISSING", "INVALID"]
    local_columns: tuple[str, ...]
    checks: tuple[AuthorityCheck, ...]


class UniverseAuthority(BaseModel):
    """D1 point-in-time membership verdict and coverage."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", allow_inf_nan=False
    )

    state: Literal["VERIFIED", "BLOCKED"]
    current_metadata_state: Literal["PRESENT", "MISSING", "INVALID"]
    pit_membership_state: Literal["PRESENT", "MISSING", "INVALID"]
    daily_table_count: int = Field(ge=0)
    required_membership_pairs: int = Field(ge=0)
    covered_membership_pairs: int = Field(ge=0)
    coverage_percent: float = Field(ge=0, le=100)
    checks: tuple[AuthorityCheck, ...]


class MarketAuthorityReceipt(BaseModel):
    """Combined fail-closed receipt consumed by research and dashboard surfaces."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[
        "kronos_daily_market_authority.v2",
        "kronos_daily_market_authority.v3",
    ]
    research_id: Literal[
        "DAILY_MARKET_AUTHORITY_2026_08_10_001",
        "DAILY_MARKET_AUTHORITY_2026_08_10_002",
        "DAILY_MARKET_AUTHORITY_2026_08_14_003",
    ]
    status: Literal["VERIFIED_RESEARCH_DATA_AUTHORITY", "BLOCKED_DATA_AUTHORITY"]
    daily_database: AuthorityFileIdentity
    input_bindings: tuple[AuthorityInputBinding, ...]
    source_artifacts: tuple[AuthorityFileIdentity, ...]
    d0_price_basis: PriceBasisAuthority
    d1_universe: UniverseAuthority
    blockers: tuple[str, ...]
    source_urls: tuple[str, ...]
    verified_at_utc: str = "1970-01-01T00:00:00Z"
    reviewer_trust_store_sha256: str = Field(
        default=PINNED_REVIEWER_TRUST_STORE_SHA256,
        pattern=r"^[0-9a-f]{64}$",
    )
    reviewer_trust_store: ReviewerTrustStore = Field(
        default_factory=_empty_reviewer_trust_store
    )
    signed_extraction_reviews: tuple[SignedExtractionReviewProof, ...] = ()
    historical_test_state: Literal[
        "FEATURES_PARSED_REWARDS_PRICES_ACTION_EVALUATION_NOT_READ_CONTAMINATED"
    ]
    fresh_oos_read: Literal[False]
    promotion_allowed: Literal[False]
    live_ready: Literal[False]

    @model_validator(mode="after")
    def _authority_verdict_is_canonical(self) -> Self:
        expected_roles = {
            "DAILY_DATABASE",
            "STOCKINFO_DATABASE",
            "CANDIDATE_SCORES",
            "PRICE_PROVENANCE",
            "CURRENT_OFFICIAL_METADATA",
            "PIT_MEMBERSHIP",
        }
        bindings = {binding.role: binding for binding in self.input_bindings}
        if len(bindings) != len(self.input_bindings) or set(bindings) != expected_roles:
            raise ValueError("authority receipt requires six unique input bindings")
        daily_binding = bindings["DAILY_DATABASE"]
        if (
            daily_binding.state != "PRESENT"
            or daily_binding.identity != self.daily_database
        ):
            raise ValueError("daily database identity is not canonical")
        expected_blockers = tuple(
            blocker
            for blocker, verified in (
                (
                    "D0_PRICE_BASIS_NOT_VERIFIED",
                    self.d0_price_basis.state == "VERIFIED",
                ),
                (
                    "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED",
                    self.d1_universe.state == "VERIFIED",
                ),
            )
            if not verified
        )
        if self.blockers != expected_blockers:
            raise ValueError("authority blockers do not match D0/D1 states")
        verified = not expected_blockers
        if (self.status == "VERIFIED_RESEARCH_DATA_AUTHORITY") != verified:
            raise ValueError("authority status does not match D0/D1 states")
        if self.schema_version == "kronos_daily_market_authority.v2":
            if verified or self.signed_extraction_reviews:
                raise ValueError("legacy authority receipt cannot be verified")
            return self
        trust_bytes = canonical_bytes(self.reviewer_trust_store)
        if (
            hashlib.sha256(trust_bytes).hexdigest() != self.reviewer_trust_store_sha256
            or self.reviewer_trust_store_sha256 != PINNED_REVIEWER_TRUST_STORE_SHA256
        ):
            raise ValueError("reviewer trust store is not pinned")
        if verified:
            expected_d0_checks = (
                "ALL_DAILY_TABLES_EXPLICIT_PRICE_BASIS",
                "INDEPENDENT_PROVENANCE_PRESENT",
                "PROVENANCE_BINDS_DATABASE_SHA256",
                "PROVENANCE_SOURCE_REVIEW_VERIFIED",
            )
            expected_d1_checks = (
                "STOCKINFO_METADATA_PRESENT",
                "CURRENT_OFFICIAL_METADATA_PRESENT",
                "PIT_MEMBERSHIP_COMPLETE_AND_AVAILABLE",
                "KRX_SOURCE_REVIEWS_VERIFIED",
            )
            if (
                tuple(check.check_id for check in self.d0_price_basis.checks)
                != expected_d0_checks
                or not all(check.passed for check in self.d0_price_basis.checks)
                or self.d0_price_basis.price_basis == "unknown"
            ):
                raise ValueError("verified D0 checks are not canonical")
            if (
                tuple(check.check_id for check in self.d1_universe.checks)
                != expected_d1_checks
                or not all(check.passed for check in self.d1_universe.checks)
                or self.d1_universe.current_metadata_state != "PRESENT"
                or self.d1_universe.pit_membership_state != "PRESENT"
                or self.d1_universe.required_membership_pairs <= 0
                or self.d1_universe.covered_membership_pairs
                != self.d1_universe.required_membership_pairs
                or self.d1_universe.coverage_percent != 100.0
            ):
                raise ValueError("verified D1 checks are not canonical")
            if any(binding.state != "PRESENT" for binding in bindings.values()):
                raise ValueError("verified authority requires every input binding")
            if not self.source_artifacts:
                raise ValueError("verified authority requires source artifacts")
            source_hashes = {identity.sha256 for identity in self.source_artifacts}
            if len(source_hashes) != len(self.source_artifacts) or any(
                identity.path_suffix != f"{identity.sha256}.source"
                for identity in self.source_artifacts
            ):
                raise ValueError("verified source artifacts are not canonical")
            scope_roles: dict[ReviewerScope, AuthorityInputRole] = {
                "D0_PRICE_PROVENANCE": "PRICE_PROVENANCE",
                "D1_CURRENT_METADATA": "CURRENT_OFFICIAL_METADATA",
                "D1_PIT_MEMBERSHIP": "PIT_MEMBERSHIP",
            }
            proofs = {
                proof.review.statement.scope: proof
                for proof in self.signed_extraction_reviews
            }
            if set(proofs) != set(scope_roles) or len(proofs) != len(
                self.signed_extraction_reviews
            ):
                raise ValueError("verified authority requires three unique reviews")
            receipt_ids = tuple(
                proof.review.statement.receipt_id for proof in proofs.values()
            )
            nonces = tuple(proof.review.statement.nonce for proof in proofs.values())
            if len(set(receipt_ids)) != 3 or len(set(nonces)) != 3:
                raise ValueError("signed reviews require unique receipt IDs and nonces")
            verification_time = datetime.fromisoformat(
                self.verified_at_utc.replace("Z", "+00:00")
            )
            sources = {identity.sha256: identity for identity in self.source_artifacts}
            for scope, role in scope_roles.items():
                proof = proofs[scope]
                review_bytes = canonical_bytes(proof.review)
                if (
                    hashlib.sha256(review_bytes).hexdigest() != proof.receipt_sha256
                    or len(review_bytes) != proof.receipt_size_bytes
                ):
                    raise ValueError("signed review receipt identity mismatch")
                target = bindings[role].identity
                if target is None:
                    raise ValueError("signed review target input is absent")
                raw_bindings = tuple(
                    (raw.sha256, raw.size_bytes)
                    for raw in proof.review.statement.raw_sources
                )
                if any(
                    raw_hash not in sources or sources[raw_hash].size_bytes != raw_size
                    for raw_hash, raw_size in raw_bindings
                ):
                    raise ValueError("signed review raw source identity mismatch")
                _ = verify_extraction_review(
                    self.reviewer_trust_store,
                    proof.review,
                    expected_scope=scope,
                    target_sha256=target.sha256,
                    target_size_bytes=target.size_bytes,
                    raw_sources=raw_bindings,
                    verification_time=verification_time,
                )
        elif self.signed_extraction_reviews:
            raise ValueError("blocked authority must not publish verified reviews")
        return self


__all__ = [
    "AuthorityCheck",
    "AuthorityFileIdentity",
    "AuthorityInputBinding",
    "AuthorityInputRole",
    "DailyMarketAuthorityError",
    "MarketAuthorityReceipt",
    "PitMembershipRecord",
    "PriceBasisAuthority",
    "PriceProvenanceRecord",
    "UniverseAuthority",
]
