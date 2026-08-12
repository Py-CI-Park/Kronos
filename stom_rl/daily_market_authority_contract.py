"""Typed D0/D1 source-authority evidence for the daily-market RL lane."""

from __future__ import annotations

from typing import ClassVar, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import override


# A content hash proves byte identity, not who reviewed the upstream broker/KRX
# response.  Keep VERIFIED receipts structurally impossible until a signed
# reviewer trust root and receipt verifier are implemented.
SIGNED_SOURCE_REVIEW_SUPPORTED: Final = False


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

    schema_version: Literal["kronos_daily_market_authority.v2"]
    research_id: Literal[
        "DAILY_MARKET_AUTHORITY_2026_08_10_001",
        "DAILY_MARKET_AUTHORITY_2026_08_10_002",
    ]
    status: Literal["VERIFIED_RESEARCH_DATA_AUTHORITY", "BLOCKED_DATA_AUTHORITY"]
    daily_database: AuthorityFileIdentity
    input_bindings: tuple[AuthorityInputBinding, ...]
    source_artifacts: tuple[AuthorityFileIdentity, ...]
    d0_price_basis: PriceBasisAuthority
    d1_universe: UniverseAuthority
    blockers: tuple[str, ...]
    source_urls: tuple[str, ...]
    historical_test_read: Literal[False]
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
        if verified:
            if not SIGNED_SOURCE_REVIEW_SUPPORTED:
                raise ValueError("signed source review verification is unsupported")
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
    "SIGNED_SOURCE_REVIEW_SUPPORTED",
    "UniverseAuthority",
]
