"""Immutable D0/D1 authority summary and receipt artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

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
    summary: tuple[()]
    promotion_allowed: Literal[False]
    fresh_oos_read: Literal[False]


def _write_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    _ = temporary.write_text(text, encoding="utf-8")
    _ = temporary.replace(path)


def write_authority_artifacts(
    receipt: MarketAuthorityReceipt,
    output_directory: Path,
) -> AuthorityArtifactPaths:
    """Write a bounded catalog summary and the complete authority receipt."""
    if has_reparse_component(output_directory):
        raise DailyMarketAuthorityError("AUTHORITY_OUTPUT_UNTRUSTED")
    output_directory.mkdir(parents=True, exist_ok=True)
    if has_reparse_component(output_directory):
        raise DailyMarketAuthorityError("AUTHORITY_OUTPUT_UNTRUSTED")
    summary_path = output_directory / "summary.json"
    receipt_path = output_directory / "authority_receipt.json"
    summary = AuthorityDashboardSummary(
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
        summary=(),
        promotion_allowed=False,
        fresh_oos_read=False,
    )
    _write_text(summary_path, f"{summary.model_dump_json(indent=2)}\n")
    _write_text(receipt_path, f"{receipt.model_dump_json(indent=2)}\n")
    return AuthorityArtifactPaths(summary_path, receipt_path)


__all__ = [
    "AuthorityArtifactPaths",
    "AuthorityDashboardSummary",
    "write_authority_artifacts",
]
