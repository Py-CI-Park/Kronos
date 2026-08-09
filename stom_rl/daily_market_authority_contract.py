"""Typed D0/D1 source-authority evidence for the daily-market RL lane."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import override


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

    path_suffix: str
    size_bytes: int = Field(gt=0)
    modified_at_utc: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PriceProvenanceRecord(BaseModel):
    """Independent declaration binding collection semantics to the DB content."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_price_provenance.v1"]
    database_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_system: str = Field(min_length=1)
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

    schema_version: Literal["kronos_daily_market_authority.v1"]
    research_id: Literal["DAILY_MARKET_AUTHORITY_2026_08_10_001"]
    status: Literal["VERIFIED_RESEARCH_DATA_AUTHORITY", "BLOCKED_DATA_AUTHORITY"]
    daily_database: AuthorityFileIdentity
    d0_price_basis: PriceBasisAuthority
    d1_universe: UniverseAuthority
    blockers: tuple[str, ...]
    source_urls: tuple[str, ...]
    historical_test_read: Literal[False]
    fresh_oos_read: Literal[False]
    promotion_allowed: Literal[False]
    live_ready: Literal[False]


__all__ = [
    "AuthorityCheck",
    "AuthorityFileIdentity",
    "DailyMarketAuthorityError",
    "MarketAuthorityReceipt",
    "PitMembershipRecord",
    "PriceBasisAuthority",
    "PriceProvenanceRecord",
    "UniverseAuthority",
]
