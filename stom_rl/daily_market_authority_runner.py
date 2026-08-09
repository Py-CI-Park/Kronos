"""Registered CLI boundary for the D0/D1 authority audit."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from .daily_market_authority_artifacts import (
    AuthorityArtifactPaths,
    write_authority_artifacts,
)
from .daily_market_authority_audit import MarketAuthorityInputs, audit_market_authority
from .daily_market_authority_contract import (
    DailyMarketAuthorityError,
    MarketAuthorityReceipt,
)


@dataclass(frozen=True, slots=True)
class DailyMarketAuthorityPaths:
    """Fixed audit inputs and generated output directory."""

    repository_root: Path
    daily_database: Path
    stockinfo_database: Path
    candidate_scores: Path
    price_provenance: Path
    current_official_metadata: Path
    pit_membership: Path
    output_directory: Path

    @classmethod
    def registered(cls, repository_root: Path) -> DailyMarketAuthorityPaths:
        root = repository_root.resolve()
        dataset = (
            root
            / "webui"
            / "rl_runs"
            / "daily_close_slot_dataset"
            / "daily_close_slot_research_dataset_2026_07_03"
        )
        return cls(
            repository_root=root,
            daily_database=root / "_database" / "Stock_Database_ohlcv_1day.db",
            stockinfo_database=root / "_database" / "stock_tick_back.db",
            candidate_scores=dataset / "candidate_score_rows.csv",
            price_provenance=root / "_database" / "daily_price_provenance.json",
            current_official_metadata=root / "_database" / "krx_listed_products.csv",
            pit_membership=root / "_database" / "krx_pit_membership.csv",
            output_directory=(
                root
                / "webui"
                / "rl_runs"
                / "daily_market_authority"
                / "DAILY_MARKET_AUTHORITY_2026_08_10_001"
            ),
        )


@dataclass(frozen=True, slots=True)
class CompletedAuthorityAudit:
    """Completed receipt and durable evidence locations."""

    receipt: MarketAuthorityReceipt
    artifacts: AuthorityArtifactPaths


class AuthorityCompletionEvent(BaseModel):
    """Compact stdout boundary for automation and operator inspection."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    event: Literal["AUTHORITY_AUDIT_COMPLETED"]
    status: Literal["VERIFIED_RESEARCH_DATA_AUTHORITY", "BLOCKED_DATA_AUTHORITY"]
    d0_price_basis: Literal["VERIFIED", "BLOCKED"]
    d1_universe: Literal["VERIFIED", "BLOCKED"]
    summary_path: str
    receipt_path: str
    historical_test_read: Literal[False]
    fresh_oos_read: Literal[False]
    promotion_allowed: Literal[False]


def run_authority_audit(paths: DailyMarketAuthorityPaths) -> CompletedAuthorityAudit:
    """Run the registered read-only audit and publish its evidence."""
    receipt = audit_market_authority(
        MarketAuthorityInputs(
            daily_database=paths.daily_database,
            stockinfo_database=paths.stockinfo_database,
            candidate_scores=paths.candidate_scores,
            price_provenance=paths.price_provenance,
            current_official_metadata=paths.current_official_metadata,
            pit_membership=paths.pit_membership,
        )
    )
    artifacts = write_authority_artifacts(receipt, paths.output_directory)
    return CompletedAuthorityAudit(receipt=receipt, artifacts=artifacts)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the registered read-only audit; optional first arg is repository root."""
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if len(arguments) > 1:
        raise DailyMarketAuthorityError("RUNNER_ACCEPTS_AT_MOST_ONE_REPOSITORY_ROOT")
    repository_root = (
        Path(arguments[0]) if arguments else Path(__file__).resolve().parents[1]
    )
    result = run_authority_audit(DailyMarketAuthorityPaths.registered(repository_root))
    print(
        AuthorityCompletionEvent(
            event="AUTHORITY_AUDIT_COMPLETED",
            status=result.receipt.status,
            d0_price_basis=result.receipt.d0_price_basis.state,
            d1_universe=result.receipt.d1_universe.state,
            summary_path=str(result.artifacts.summary.resolve()),
            receipt_path=str(result.artifacts.receipt.resolve()),
            historical_test_read=False,
            fresh_oos_read=False,
            promotion_allowed=False,
        ).model_dump_json(),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AuthorityCompletionEvent",
    "CompletedAuthorityAudit",
    "DailyMarketAuthorityPaths",
    "run_authority_audit",
]
