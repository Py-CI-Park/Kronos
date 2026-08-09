"""Registered end-to-end runner for actual-market DQN/CQL research."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from .daily_market_rl_artifacts import ExperimentArtifactPaths, write_experiment_artifacts
from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_rl_dataset import prepare_market_data
from .daily_market_rl_experiment import ModelArmPlan, train_model_arms
from .daily_market_rl_experiment_contract import MarketExperimentExecution
from .daily_market_rl_finalization import finalize_experiment
from .daily_market_score_dataset import load_market_score_dataset
from .daily_market_state_dataset import build_market_state_dataset


@dataclass(frozen=True, slots=True)
class DailyMarketExperimentPaths:
    """Fixed source and generated-artifact locations for the registered run."""

    repository_root: Path
    dataset_root: Path
    candidate_scores: Path
    source_manifest: Path
    causal_panel: Path
    daily_database: Path
    output_directory: Path

    @classmethod
    def registered(cls, repository_root: Path) -> DailyMarketExperimentPaths:
        root = repository_root.resolve()
        dataset = (
            root
            / "webui"
            / "rl_runs"
            / "daily_close_slot_dataset"
            / "daily_close_slot_research_dataset_2026_07_03"
        )
        output = (
            root
            / "webui"
            / "rl_runs"
            / "daily_market_offline_rl"
            / "DAILY_MARKET_CQL_2026_08_09_001"
        )
        return cls(
            repository_root=root,
            dataset_root=dataset,
            candidate_scores=dataset / "candidate_score_rows.csv",
            source_manifest=dataset / "close_slot_dataset_manifest.json",
            causal_panel=dataset / "close_slot_panel.csv",
            daily_database=root / "_database" / "Stock_Database_ohlcv_1day.db",
            output_directory=output,
        )


@dataclass(frozen=True, slots=True)
class RegisteredExperimentRun:
    """Completed in-memory receipt plus generated artifact paths."""

    execution: MarketExperimentExecution
    artifacts: ExperimentArtifactPaths


class ModelProgressEvent(BaseModel):
    """One line emitted after each completed training arm."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    event: Literal["MODEL_COMPLETED"]
    algorithm: str
    seed: int = Field(ge=0)
    completed_models: int = Field(ge=1, le=20)
    total_models: Literal[20]
    elapsed_seconds: float = Field(ge=0)


class ExperimentCompletionEvent(BaseModel):
    """Final compact CLI output after artifacts are durable."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    event: Literal["EXPERIMENT_COMPLETED"]
    verdict: str
    summary_path: str
    receipt_path: str
    action_ledger_path: str
    fresh_oos_state: Literal["NOT_RUN_NO_READ"]
    promotion_allowed: Literal[False]


def run_registered_experiment(
    paths: DailyMarketExperimentPaths,
    *,
    on_model_completed: Callable[[ModelArmPlan, float], None] | None = None,
) -> RegisteredExperimentRun:
    """Train first, open historical TEST once, then finalize immutable evidence."""
    if paths.output_directory.is_symlink():
        raise DailyMarketRlContractError("EXPERIMENT_OUTPUT_SYMLINK_REJECTED")
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
    train_validation = prepare_market_data(
        scores,
        states,
        db_path=paths.daily_database,
        read_splits=("TRAIN", "VALIDATION"),
    )
    behavior_count, trained = train_model_arms(
        train_validation,
        output_directory=paths.output_directory,
        on_completed=on_model_completed,
    )
    historical_test = prepare_market_data(
        scores,
        states,
        db_path=paths.daily_database,
        read_splits=("TEST",),
    )
    execution = finalize_experiment(
        train_validation,
        historical_test,
        states,
        trained,
        behavior_transition_count=behavior_count,
    )
    artifacts = write_experiment_artifacts(execution, paths.output_directory)
    return RegisteredExperimentRun(execution, artifacts)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the one registered experiment; optional first arg is repository root."""
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if len(arguments) > 1:
        raise DailyMarketRlContractError("RUNNER_ACCEPTS_AT_MOST_ONE_REPOSITORY_ROOT")
    repository_root = (
        Path(arguments[0])
        if arguments
        else Path(__file__).resolve().parents[1]
    )
    completed = 0

    def report(plan: ModelArmPlan, elapsed_seconds: float) -> None:
        nonlocal completed
        completed += 1
        print(
            ModelProgressEvent(
                event="MODEL_COMPLETED",
                algorithm=plan.algorithm.value,
                seed=plan.seed,
                completed_models=completed,
                total_models=20,
                elapsed_seconds=elapsed_seconds,
            ).model_dump_json(),
            flush=True,
        )

    result = run_registered_experiment(
        DailyMarketExperimentPaths.registered(repository_root),
        on_model_completed=report,
    )
    print(
        ExperimentCompletionEvent(
            event="EXPERIMENT_COMPLETED",
            verdict=result.execution.receipt.verdict,
            summary_path=str(result.artifacts.summary.resolve()),
            receipt_path=str(result.artifacts.receipt.resolve()),
            action_ledger_path=str(result.artifacts.action_ledger.resolve()),
            fresh_oos_state="NOT_RUN_NO_READ",
            promotion_allowed=False,
        ).model_dump_json(),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DailyMarketExperimentPaths",
    "RegisteredExperimentRun",
    "run_registered_experiment",
]
