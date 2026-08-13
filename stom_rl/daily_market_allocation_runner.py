"""Registered end-to-end runner for validation-only four-action RL screening."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

from .daily_market_allocation_artifacts import write_allocation_artifacts
from .daily_market_allocation_custody import (
    assert_allocation_inputs_unchanged,
    capture_allocation_input_snapshot,
    ensure_allocation_output_available,
    immutable_allocation_database_snapshot,
    load_allocation_authority,
)
from .daily_market_allocation_experiment import (
    AllocationModelPlan,
    train_allocation_arms,
)
from .daily_market_allocation_finalization import finalize_allocation_screen
from .daily_market_allocation_lineage import build_registered_allocation_lineage
from .daily_market_allocation_reproduction import (
    load_allocation_reproduction_reference,
)
from .daily_market_allocation_input_snapshot import immutable_allocation_direct_inputs
from .daily_market_allocation_run_contract import (
    AllocationCompletionEvent,
    AllocationInputSnapshot,
    AllocationModelProgressEvent,
    DailyMarketAllocationPaths,
    RegisteredAllocationRun,
)
from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_rl_dataset import prepare_market_data
from .daily_market_score_dataset import (
    DailyMarketScoreDataset,
    load_market_score_dataset,
)
from .daily_market_state_dataset import (
    DailyMarketStateDataset,
    build_market_state_dataset,
)


def load_allocation_direct_datasets(
    frozen_inputs: DailyMarketAllocationPaths,
) -> tuple[DailyMarketScoreDataset, DailyMarketStateDataset]:
    """Load all small market inputs from one immutable snapshot directory."""
    frozen_artifact_root = frozen_inputs.candidate_scores.parent
    scores = load_market_score_dataset(
        frozen_inputs.candidate_scores,
        source_manifest_path=frozen_inputs.source_manifest,
        artifact_root=frozen_artifact_root,
    )
    states = build_market_state_dataset(
        scores,
        panel_csv_path=frozen_inputs.causal_panel,
        artifact_root=frozen_artifact_root,
    )
    return scores, states


def run_registered_allocation_screen(
    paths: DailyMarketAllocationPaths,
    *,
    on_model_completed: Callable[[AllocationModelPlan, float], None] | None = None,
) -> RegisteredAllocationRun:
    """Train/validate ten models with contaminated TEST features and unread rewards."""
    ensure_allocation_output_available(paths.output_directory)
    input_snapshot = capture_allocation_input_snapshot(paths)
    lineage = build_registered_allocation_lineage(input_snapshot)
    with immutable_allocation_direct_inputs(paths, input_snapshot) as frozen_inputs:
        reference_receipt = load_allocation_reproduction_reference(
            frozen_inputs.source_allocation_receipt,
            expected_sha256=next(
                sha256
                for role, sha256 in input_snapshot.rows
                if role == "SOURCE_ALLOCATION_RECEIPT_001"
            ),
        )
        authority_paths = replace(
            paths,
            authority_receipt=frozen_inputs.authority_receipt,
        )
        authority = load_allocation_authority(authority_paths)
        with immutable_allocation_database_snapshot(
            paths,
            authority.daily_database.sha256,
        ) as database_snapshot:
            scores, states = load_allocation_direct_datasets(frozen_inputs)
            prepared = prepare_market_data(
                scores,
                states,
                db_path=database_snapshot,
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
                lineage=lineage,
                reference_receipt=reference_receipt,
            )
    assert_allocation_inputs_unchanged(paths, input_snapshot)
    _ = load_allocation_authority(paths)
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
            telemetry_path=str(result.artifacts.telemetry.resolve()),
            bundle_manifest_path=str(result.artifacts.bundle_manifest.resolve()),
            authority_status=receipt.authority_status,
            historical_test_state=receipt.historical_test_state,
            fresh_oos_state="NOT_RUN_NO_READ",
            promotion_allowed=False,
        ).model_dump_json(),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AllocationInputSnapshot",
    "DailyMarketAllocationPaths",
    "RegisteredAllocationRun",
    "assert_allocation_inputs_unchanged",
    "capture_allocation_input_snapshot",
    "ensure_allocation_output_available",
    "immutable_allocation_database_snapshot",
    "load_allocation_direct_datasets",
    "run_registered_allocation_screen",
]
