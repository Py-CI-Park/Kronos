"""Typed statements and trust roots for signed market-authority reviews."""

from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from typing import ClassVar, Literal, Self, cast
from uuid import UUID

import rfc8785  # pyright: ignore[reportMissingImports]
from pydantic import BaseModel, ConfigDict, Field, model_validator

SIGNING_DOMAIN = b"KRONOS-DAILY-MARKET-EXTRACTION-REVIEW-V1\x00"
ReviewerScope = Literal[
    "D0_PRICE_PROVENANCE",
    "D1_CURRENT_METADATA",
    "D1_PIT_MEMBERSHIP",
]
ReviewerRole = Literal["D0_REVIEWER", "D1_REVIEWER"]
NormalizedRole = Literal[
    "PRICE_PROVENANCE", "CURRENT_OFFICIAL_METADATA", "PIT_MEMBERSHIP"
]
_B64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def parse_utc_seconds(value: str) -> datetime:
    if not value.endswith("Z") or "." in value:
        raise ValueError("timestamp must be UTC seconds with Z suffix")
    parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    if (
        parsed.tzinfo != timezone.utc
        or parsed.isoformat(timespec="seconds") != value.removesuffix("Z") + "+00:00"
    ):
        raise ValueError("timestamp is not canonical UTC seconds")
    return parsed


def canonical_uuid(value: str) -> str:
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError("UUID is not canonical")
    return value


def decode_base64url(value: str, expected_bytes: int) -> bytes:
    if not _B64URL_RE.fullmatch(value) or "=" in value:
        raise ValueError("base64url value is not canonical")
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if len(decoded) != expected_bytes:
        raise ValueError("base64url value has wrong length")
    if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
        raise ValueError("base64url value is not canonical")
    return decoded


class ReviewerTrustKey(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    principal_uri: str = Field(pattern=r"^reviewer://[A-Za-z0-9._/-]+$")
    key_id: str
    role: ReviewerRole
    scopes: tuple[ReviewerScope, ...]
    algorithm: Literal["Ed25519"]
    public_key_encoding: Literal["base64url-no-pad"]
    public_key: str
    not_before_utc: str
    not_after_utc: str
    status: Literal["ACTIVE", "REVOKED"]
    revoked_at_utc: str | None = None

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        _ = canonical_uuid(self.key_id)
        _ = decode_base64url(self.public_key, 32)
        start = parse_utc_seconds(self.not_before_utc)
        end = parse_utc_seconds(self.not_after_utc)
        if start >= end or tuple(sorted(set(self.scopes))) != self.scopes:
            raise ValueError("trust-key validity or scopes are not canonical")
        if (self.status == "ACTIVE") != (self.revoked_at_utc is None):
            raise ValueError("trust-key revocation state is inconsistent")
        if self.revoked_at_utc is not None:
            _ = parse_utc_seconds(self.revoked_at_utc)
        return self


class ReviewerTrustStore(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", populate_by_name=True
    )

    schema_version: Literal["kronos_daily_market_reviewer_trust.v1"] = Field(
        alias="schema"
    )
    keys: tuple[ReviewerTrustKey, ...]

    @model_validator(mode="after")
    def _unique(self) -> Self:
        identities = tuple((key.principal_uri, key.key_id) for key in self.keys)
        if tuple(sorted(identities)) != identities or len(set(identities)) != len(
            identities
        ):
            raise ValueError("trust keys must be sorted and unique")
        return self


class RawSourceReviewBinding(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    source_system: Literal["KIWOOM_OPENAPI", "KRX_DATA_PORTAL"]
    source_url: str = Field(pattern=r"^https://")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    available_at_utc: str

    @model_validator(mode="after")
    def _time(self) -> Self:
        _ = parse_utc_seconds(self.available_at_utc)
        return self


class NormalizedTargetReviewBinding(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    role: NormalizedRole
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    normalization_profile: Literal[
        "KIWOOM_OPT10081_PRICE_PROVENANCE_V1",
        "KRX_CURRENT_COMMON_EQUITY_V1",
        "KRX_PIT_COMMON_EQUITY_V1",
    ]


class ExtractionReviewPolicy(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    policy_id: Literal["KRONOS_DAILY_MARKET_AUTHORITY_EXTRACTION"]
    policy_version: Literal["1"]
    evidence_kind: Literal["REAL"]
    review_decision: Literal["APPROVE"]


class ExtractionReviewStatement(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", populate_by_name=True
    )

    schema_version: Literal["kronos_daily_market_extraction_review.v1"] = Field(
        alias="schema"
    )
    receipt_id: str
    nonce: str
    scope: ReviewerScope
    reviewer_principal: str = Field(pattern=r"^reviewer://[A-Za-z0-9._/-]+$")
    reviewer_key_id: str
    reviewed_at_utc: str
    raw_sources: tuple[RawSourceReviewBinding, ...]
    normalized_target: NormalizedTargetReviewBinding
    policy: ExtractionReviewPolicy

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        _ = canonical_uuid(self.receipt_id)
        _ = canonical_uuid(self.reviewer_key_id)
        _ = decode_base64url(self.nonce, 32)
        reviewed_at = parse_utc_seconds(self.reviewed_at_utc)
        hashes = tuple(source.sha256 for source in self.raw_sources)
        if (
            not hashes
            or tuple(sorted(hashes)) != hashes
            or len(set(hashes)) != len(hashes)
        ):
            raise ValueError("raw sources must be sorted, nonempty, and unique")
        if any(
            parse_utc_seconds(source.available_at_utc) > reviewed_at
            for source in self.raw_sources
        ):
            raise ValueError("raw source became available after review")
        return self


class SignedExtractionReview(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    statement: ExtractionReviewStatement
    signature: str


class SignedExtractionReviewProof(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_size_bytes: int = Field(gt=0)
    review: SignedExtractionReview


def canonical_bytes(model: BaseModel) -> bytes:
    return cast(
        bytes,
        rfc8785.dumps(  # pyright: ignore[reportUnknownMemberType]
            model.model_dump(mode="json", by_alias=True)
        ),
    )


__all__ = [
    "SIGNING_DOMAIN",
    "ExtractionReviewPolicy",
    "ExtractionReviewStatement",
    "NormalizedTargetReviewBinding",
    "RawSourceReviewBinding",
    "ReviewerScope",
    "ReviewerTrustKey",
    "ReviewerTrustStore",
    "SignedExtractionReview",
    "SignedExtractionReviewProof",
    "canonical_bytes",
    "decode_base64url",
    "parse_utc_seconds",
]
