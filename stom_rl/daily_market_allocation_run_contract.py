"""Typed paths and process events for the registered allocation screen."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from .daily_market_allocation_artifacts import AllocationArtifactPaths
from .daily_market_allocation_experiment_contract import AllocationExperimentExecution
from .daily_market_allocation_lineage_contract import AllocationLineageInputRole


@dataclass(frozen=True, slots=True)
class DailyMarketAllocationPaths:
    repository_root: Path
    dataset_root: Path
    candidate_scores: Path
    source_manifest: Path
    causal_panel: Path
    daily_database: Path
    stockinfo_database: Path
    price_provenance: Path
    current_official_metadata: Path
    pit_membership: Path
    source_artifact_root: Path
    authority_receipt: Path
    source_allocation_receipt: Path
    output_directory: Path

    @classmethod
    def registered(cls, repository_root: Path) -> DailyMarketAllocationPaths:
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
            dataset_root=dataset,
            candidate_scores=dataset / "candidate_score_rows.csv",
            source_manifest=dataset / "close_slot_dataset_manifest.json",
            causal_panel=dataset / "close_slot_panel.csv",
            daily_database=root / "_database" / "Stock_Database_ohlcv_1day.db",
            stockinfo_database=root / "_database" / "stock_tick_back.db",
            price_provenance=root / "_database" / "daily_price_provenance.json",
            current_official_metadata=root / "_database" / "krx_listed_products.csv",
            pit_membership=root / "_database" / "krx_pit_membership.csv",
            source_artifact_root=root / "_database" / "market_authority_sources",
            authority_receipt=(
                root
                / "webui"
                / "rl_runs"
                / "daily_market_authority"
                / "DAILY_MARKET_AUTHORITY_2026_08_10_002"
                / "authority_receipt.json"
            ),
            source_allocation_receipt=(
                root
                / "webui"
                / "rl_runs"
                / "daily_market_allocation"
                / "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001"
                / "validation_receipt.json"
            ),
            output_directory=(
                root
                / "webui"
                / "rl_runs"
                / "daily_market_allocation"
                / "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002"
            ),
        )


@dataclass(frozen=True, slots=True)
class RegisteredAllocationRun:
    execution: AllocationExperimentExecution
    artifacts: AllocationArtifactPaths


@dataclass(frozen=True, slots=True)
class AllocationInputSnapshot:
    rows: tuple[tuple[AllocationLineageInputRole, str], ...]


class AllocationModelProgressEvent(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    event: Literal["ALLOCATION_MODEL_COMPLETED"]
    algorithm: str
    seed: int = Field(ge=0)
    completed_models: int = Field(ge=1, le=10)
    total_models: Literal[10]
    elapsed_seconds: float = Field(ge=0)


class AllocationCompletionEvent(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    event: Literal["ALLOCATION_SCREEN_COMPLETED"]
    verdict: Literal[
        "VALIDATION_CANDIDATE",
        "NO_GO_VALIDATION_SCREEN",
        "REPRODUCTION_ONLY_VALIDATION_CONSUMED",
        "REPRODUCTION_MISMATCH_VALIDATION_CONSUMED",
    ]
    summary_path: str
    receipt_path: str
    ledger_path: str
    telemetry_path: str
    bundle_manifest_path: str
    authority_status: str
    historical_test_state: Literal[
        "NOT_RUN_NO_READ",
        "FEATURES_PARSED_REWARDS_NOT_READ_CONTAMINATED",
    ]
    fresh_oos_state: Literal["NOT_RUN_NO_READ"]
    promotion_allowed: Literal[False]


__all__ = [
    "AllocationCompletionEvent",
    "AllocationInputSnapshot",
    "AllocationModelProgressEvent",
    "DailyMarketAllocationPaths",
    "RegisteredAllocationRun",
]
