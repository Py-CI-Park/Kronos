"""Registered end-to-end runner for validation-only four-action RL screening."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .daily_market_allocation_artifacts import (
    AllocationArtifactPaths,
    write_allocation_artifacts,
)
from .daily_market_allocation_experiment import (
    AllocationModelPlan,
    train_allocation_arms,
)
from .daily_market_allocation_experiment_contract import AllocationExperimentExecution
from .daily_market_allocation_finalization import finalize_allocation_screen
from .daily_market_authority_contract import MarketAuthorityReceipt
from .daily_market_authority_sources import file_identity
from .daily_market_path_custody import has_reparse_component
from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_rl_dataset import prepare_market_data
from .daily_market_score_dataset import load_market_score_dataset
from .daily_market_state_dataset import build_market_state_dataset


@dataclass(frozen=True, slots=True)
class DailyMarketAllocationPaths:
    repository_root: Path
    dataset_root: Path
    candidate_scores: Path
    source_manifest: Path
    causal_panel: Path
    daily_database: Path
    authority_receipt: Path
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
            authority_receipt=(
                root
                / "webui"
                / "rl_runs"
                / "daily_market_authority"
                / "DAILY_MARKET_AUTHORITY_2026_08_10_001"
                / "authority_receipt.json"
            ),
            output_directory=(
                root
                / "webui"
                / "rl_runs"
                / "daily_market_allocation"
                / "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001"
            ),
        )


@dataclass(frozen=True, slots=True)
class RegisteredAllocationRun:
    execution: AllocationExperimentExecution
    artifacts: AllocationArtifactPaths


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
    verdict: Literal["VALIDATION_CANDIDATE", "NO_GO_VALIDATION_SCREEN"]
    summary_path: str
    receipt_path: str
    ledger_path: str
    authority_status: str
    historical_test_state: Literal["NOT_RUN_NO_READ"]
    fresh_oos_state: Literal["NOT_RUN_NO_READ"]
    promotion_allowed: Literal[False]


def _load_authority(paths: DailyMarketAllocationPaths) -> MarketAuthorityReceipt:
    if (
        has_reparse_component(paths.authority_receipt)
        or not paths.authority_receipt.is_file()
    ):
        raise DailyMarketRlContractError("ALLOCATION_AUTHORITY_RECEIPT_UNTRUSTED")
    try:
        receipt = MarketAuthorityReceipt.model_validate_json(
            paths.authority_receipt.read_bytes()
        )
    except (OSError, ValidationError) as exc:
        raise DailyMarketRlContractError(
            "ALLOCATION_AUTHORITY_RECEIPT_INVALID"
        ) from exc
    if file_identity(paths.daily_database).sha256 != receipt.daily_database.sha256:
        raise DailyMarketRlContractError("ALLOCATION_DATABASE_AUTHORITY_HASH_MISMATCH")
    return receipt


def run_registered_allocation_screen(
    paths: DailyMarketAllocationPaths,
    *,
    on_model_completed: Callable[[AllocationModelPlan, float], None] | None = None,
) -> RegisteredAllocationRun:
    """Train/validate ten models without opening historical TEST or Fresh OOS."""
    authority = _load_authority(paths)
    scores = load_market_score_dataset(
        paths.candidate_scores,
        source_manifest_path=paths.source_manifest,
        artifact_root=paths.dataset_root,
    )
    states = build_market_state_dataset(
        scores,
        panel_csv_path=paths.causal_panel,
        artifact_root=paths.dataset_root,
    )
    prepared = prepare_market_data(
        scores,
        states,
        db_path=paths.daily_database,
        read_splits=("TRAIN", "VALIDATION"),
    )
    behavior_count, trained = train_allocation_arms(
        prepared,
        output_directory=paths.output_directory,
        on_completed=on_model_completed,
    )
    execution = finalize_allocation_screen(
        prepared,
        authority,
        trained,
        behavior_transition_count=behavior_count,
    )
    artifacts = write_allocation_artifacts(execution, paths.output_directory)
    return RegisteredAllocationRun(execution, artifacts)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if len(arguments) > 1:
        raise DailyMarketRlContractError(
            "ALLOCATION_RUNNER_ACCEPTS_AT_MOST_ONE_REPOSITORY_ROOT"
        )
    repository_root = (
        Path(arguments[0]) if arguments else Path(__file__).resolve().parents[1]
    )
    completed = 0

    def report(plan: AllocationModelPlan, elapsed_seconds: float) -> None:
        nonlocal completed
        completed += 1
        print(
            AllocationModelProgressEvent(
                event="ALLOCATION_MODEL_COMPLETED",
                algorithm=plan.algorithm.value,
                seed=plan.seed,
                completed_models=completed,
                total_models=10,
                elapsed_seconds=elapsed_seconds,
            ).model_dump_json(),
            flush=True,
        )

    result = run_registered_allocation_screen(
        DailyMarketAllocationPaths.registered(repository_root),
        on_model_completed=report,
    )
    receipt = result.execution.receipt
    print(
        AllocationCompletionEvent(
            event="ALLOCATION_SCREEN_COMPLETED",
            verdict=receipt.verdict,
            summary_path=str(result.artifacts.summary.resolve()),
            receipt_path=str(result.artifacts.receipt.resolve()),
            ledger_path=str(result.artifacts.action_ledger.resolve()),
            authority_status=receipt.authority_status,
            historical_test_state="NOT_RUN_NO_READ",
            fresh_oos_state="NOT_RUN_NO_READ",
            promotion_allowed=False,
        ).model_dump_json(),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DailyMarketAllocationPaths",
    "RegisteredAllocationRun",
    "run_registered_allocation_screen",
]
