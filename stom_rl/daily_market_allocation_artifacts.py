"""Durable summary, receipt, and ledger artifacts for allocation screening."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .daily_market_allocation_experiment_contract import (
    AllocationDashboardRow,
    AllocationDashboardSummary,
    AllocationExperimentExecution,
)
from .daily_market_path_custody import has_reparse_component
from .daily_market_rl_contract import DailyMarketRlContractError


@dataclass(frozen=True, slots=True)
class AllocationArtifactPaths:
    summary: Path
    receipt: Path
    action_ledger: Path


def _write_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    _ = temporary.write_text(value, encoding="utf-8")
    _ = temporary.replace(path)


def _dashboard_summary(
    execution: AllocationExperimentExecution,
) -> AllocationDashboardSummary:
    receipt = execution.receipt
    rows = tuple(
        AllocationDashboardRow(
            policy=row.algorithm.value,
            seed=row.seed,
            date_count=row.validation_base.date_count,
            net_return_percent=row.validation_base.net_return_percent,
            total_net_pnl_krw=row.validation_base.total_net_pnl_krw,
            total_cost_krw=row.validation_base.total_cost_krw,
            max_drawdown_percent=row.validation_base.max_drawdown_percent,
            distinct_action_count=row.validation_base.distinct_action_count,
            action_cash_count=row.validation_base.action_cash_count,
            action_top3_count=row.validation_base.action_top3_count,
            action_top5_count=row.validation_base.action_top5_count,
            action_top10_count=row.validation_base.action_top10_count,
            mean_reward=row.validation_base.mean_reward,
            cumulative_reward=row.validation_base.cumulative_reward,
        )
        for row in receipt.model_runs
        if row.algorithm.value == "CQL"
    )
    return AllocationDashboardSummary(
        schema_version="kronos_daily_market_allocation_summary.v1",
        verdict=receipt.verdict,
        status="COMPLETE_RESEARCH_ONLY",
        algorithm="CQL",
        dataset_id=receipt.dataset_id,
        primary_headline=receipt.primary_headline,
        reasons=receipt.reasons,
        summary=rows,
        historical_test_read=False,
        promotion_allowed=False,
        fresh_oos_read=False,
    )


def write_allocation_artifacts(
    execution: AllocationExperimentExecution,
    output_directory: Path,
) -> AllocationArtifactPaths:
    """Publish bounded dashboard metadata and complete separate evidence."""
    if has_reparse_component(output_directory):
        raise DailyMarketRlContractError("ALLOCATION_OUTPUT_UNTRUSTED")
    output_directory.mkdir(parents=True, exist_ok=True)
    if has_reparse_component(output_directory):
        raise DailyMarketRlContractError("ALLOCATION_OUTPUT_UNTRUSTED")
    summary_path = output_directory / "summary.json"
    receipt_path = output_directory / "allocation_receipt.json"
    ledger_path = output_directory / "allocation_action_ledger.jsonl"
    _write_text(
        summary_path,
        f"{_dashboard_summary(execution).model_dump_json(indent=2)}\n",
    )
    _write_text(
        receipt_path,
        f"{execution.receipt.model_dump_json(indent=2)}\n",
    )
    ledger = "".join(f"{row.model_dump_json()}\n" for row in execution.trajectories)
    _write_text(ledger_path, ledger)
    return AllocationArtifactPaths(summary_path, receipt_path, ledger_path)


__all__ = [
    "AllocationArtifactPaths",
    "write_allocation_artifacts",
]
