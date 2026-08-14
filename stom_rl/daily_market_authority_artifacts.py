"""Immutable D0/D1 authority summary and receipt artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from .daily_market_authority_contract import (
    DailyMarketAuthorityError,
    MarketAuthorityReceipt,
)
from .daily_market_path_custody import has_reparse_component


@dataclass(frozen=True, slots=True)
class AuthorityArtifactPaths:
    """Durable evidence paths for one authority audit."""

    summary: Path
    receipt: Path


class AuthorityDashboardRow(BaseModel):
    """Direct D0/D1 values safe for the bounded research-detail API."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    policy: Literal["D0 PRICE BASIS", "D1 PIT UNIVERSE"]
    state: Literal["VERIFIED", "BLOCKED"]
    required_membership_pairs: int = Field(ge=0)
    covered_membership_pairs: int = Field(ge=0)
    coverage_percent: float = Field(ge=0, le=100)


class AuthorityDashboardSummary(BaseModel):
    """Bounded metadata projected into the V6 research catalog."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_authority_summary.v1"]
    verdict: Literal["VERIFIED_RESEARCH_DATA_AUTHORITY", "BLOCKED_DATA_AUTHORITY"]
    status: Literal["COMPLETE_RESEARCH_ONLY"]
    algorithm: Literal["DATA_AUTHORITY"]
    dataset_id: str
    primary_headline: str
    reasons: tuple[str, ...]
    summary: tuple[AuthorityDashboardRow, ...]
    historical_test_state: Literal[
        "FEATURES_PARSED_REWARDS_PRICES_ACTION_EVALUATION_NOT_READ_CONTAMINATED"
    ]
    promotion_allowed: Literal[False]
    fresh_oos_read: Literal[False]


def _write_text(path: Path, text: str) -> None:
    if path.exists():
        raise DailyMarketAuthorityError(
            "AUTHORITY_IMMUTABLE_ARTIFACT_ALREADY_EXISTS",
            path.name,
        )
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    if temporary.exists():
        raise DailyMarketAuthorityError(
            "AUTHORITY_TEMPORARY_ARTIFACT_ALREADY_EXISTS",
            temporary.name,
        )
    with temporary.open("x", encoding="utf-8", newline="") as handle:
        _ = handle.write(text)
    _ = temporary.rename(path)


def build_authority_dashboard_summary(
    receipt: MarketAuthorityReceipt,
) -> AuthorityDashboardSummary:
    return AuthorityDashboardSummary(
        schema_version="kronos_daily_market_authority_summary.v1",
        verdict=receipt.status,
        status="COMPLETE_RESEARCH_ONLY",
        algorithm="DATA_AUTHORITY",
        dataset_id=receipt.daily_database.sha256,
        primary_headline=(
            "D0/D1 일봉 데이터 권위 감사: VERIFIED"
            if receipt.status == "VERIFIED_RESEARCH_DATA_AUTHORITY"
            else "D0/D1 일봉 데이터 권위 감사: BLOCKED"
        ),
        reasons=receipt.blockers,
        summary=(
            AuthorityDashboardRow(
                policy="D0 PRICE BASIS",
                state=receipt.d0_price_basis.state,
                required_membership_pairs=0,
                covered_membership_pairs=0,
                coverage_percent=0.0,
            ),
            AuthorityDashboardRow(
                policy="D1 PIT UNIVERSE",
                state=receipt.d1_universe.state,
                required_membership_pairs=(
                    receipt.d1_universe.required_membership_pairs
                ),
                covered_membership_pairs=(receipt.d1_universe.covered_membership_pairs),
                coverage_percent=receipt.d1_universe.coverage_percent,
            ),
        ),
        historical_test_state=receipt.historical_test_state,
        promotion_allowed=False,
        fresh_oos_read=False,
    )


def write_authority_artifacts(
    receipt: MarketAuthorityReceipt,
    output_directory: Path,
) -> AuthorityArtifactPaths:
    """Write a bounded catalog summary and the complete authority receipt."""
    if has_reparse_component(output_directory):
        raise DailyMarketAuthorityError("AUTHORITY_OUTPUT_UNTRUSTED")
    try:
        output_directory.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise DailyMarketAuthorityError("AUTHORITY_OUTPUT_ALREADY_EXISTS") from error
    if has_reparse_component(output_directory):
        raise DailyMarketAuthorityError("AUTHORITY_OUTPUT_UNTRUSTED")
    summary_path = output_directory / "summary.json"
    receipt_path = output_directory / "authority_receipt.json"
    summary = build_authority_dashboard_summary(receipt)
    _write_text(receipt_path, f"{receipt.model_dump_json(indent=2)}\n")
    _write_text(summary_path, f"{summary.model_dump_json(indent=2)}\n")
    return AuthorityArtifactPaths(summary_path, receipt_path)


__all__ = [
    "AuthorityArtifactPaths",
    "AuthorityDashboardRow",
    "AuthorityDashboardSummary",
    "build_authority_dashboard_summary",
    "write_authority_artifacts",
]
