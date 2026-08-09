"""Bounded dashboard summary and separate ledgers for actual-market RL."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from .daily_market_path_custody import has_reparse_component
from .daily_market_rl_contract import DailyMarketRlContractError, MarketAlgorithm
from .daily_market_rl_evaluation import MarketPolicyMetrics, MarketTrajectoryStep
from .daily_market_rl_experiment_contract import (
    DashboardExperimentSummary,
    DashboardSummaryRow,
    MarketExperimentExecution,
    MarketExperimentReceipt,
)


@dataclass(frozen=True, slots=True)
class ExperimentArtifactPaths:
    """Paths written by one completed experiment."""

    summary: Path
    receipt: Path
    action_ledger: Path


class ActionLedgerRow(BaseModel):
    """One line in the separate action-level JSONL evidence."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    algorithm: str
    seed: int | None
    scenario: str
    step: MarketTrajectoryStep


def _summary_row(label: str, metrics: MarketPolicyMetrics) -> DashboardSummaryRow:
    return DashboardSummaryRow(
        policy=label,
        date_count=metrics.date_count,
        total_net_pnl_krw=metrics.total_net_pnl_krw,
        total_cost_krw=metrics.total_cost_krw,
        mean_reward=metrics.mean_reward,
        cumulative_reward=metrics.cumulative_reward,
    )


def build_dashboard_summary(
    receipt: MarketExperimentReceipt,
) -> DashboardExperimentSummary:
    """Project only controls plus native DQN/CQL into at most sixteen rows."""
    rows = [
        _summary_row(metrics.policy, metrics)
        for metrics in receipt.controls_historical_test_base
    ]
    rows.extend(
        _summary_row(
            f"{model.algorithm.value}/seed-{model.seed}",
            model.historical_test_base,
        )
        for model in receipt.model_runs
        if model.algorithm in {MarketAlgorithm.DQN, MarketAlgorithm.CQL}
    )
    return DashboardExperimentSummary(
        schema_version="kronos_daily_market_dashboard_summary.v1",
        verdict=receipt.verdict,
        status=receipt.status,
        algorithm="CQL",
        dataset_id=receipt.dataset_id,
        primary_headline=receipt.primary_headline,
        reasons=receipt.reasons[:6],
        summary=tuple(rows[:16]),
        promotion_allowed=False,
        fresh_oos_read=False,
    )


def _write_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    _ = temporary.write_text(text, encoding="utf-8")
    _ = temporary.replace(path)


def write_experiment_artifacts(
    execution: MarketExperimentExecution,
    output_directory: Path,
) -> ExperimentArtifactPaths:
    """Write summary, full receipt, and action JSONL without mixing their scopes."""
    if has_reparse_component(output_directory):
        raise DailyMarketRlContractError("EXPERIMENT_OUTPUT_UNTRUSTED")
    output_directory.mkdir(parents=True, exist_ok=True)
    if has_reparse_component(output_directory):
        raise DailyMarketRlContractError("EXPERIMENT_OUTPUT_UNTRUSTED")
    summary_path = output_directory / "summary.json"
    receipt_path = output_directory / "experiment_receipt.json"
    ledger_path = output_directory / "action_ledger.jsonl"
    summary = build_dashboard_summary(execution.receipt)
    _write_text(summary_path, f"{summary.model_dump_json(indent=2)}\n")
    _write_text(receipt_path, f"{execution.receipt.model_dump_json(indent=2)}\n")
    ledger_lines = tuple(
        ActionLedgerRow(
            algorithm=row.algorithm,
            seed=row.seed,
            scenario=row.scenario,
            step=step,
        ).model_dump_json()
        for row in execution.trajectories
        for step in row.trajectory.steps
    )
    _write_text(ledger_path, "".join(f"{line}\n" for line in ledger_lines))
    return ExperimentArtifactPaths(summary_path, receipt_path, ledger_path)


__all__ = [
    "ActionLedgerRow",
    "ExperimentArtifactPaths",
    "build_dashboard_summary",
    "write_experiment_artifacts",
]
