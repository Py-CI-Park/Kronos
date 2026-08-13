"""Durable summary, receipt, and ledger artifacts for allocation screening."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from .daily_market_allocation_experiment_contract import (
    AllocationDashboardRow,
    AllocationDashboardSummary,
    AllocationExperimentExecution,
    AllocationExperimentReceipt,
)
from .daily_market_allocation_telemetry import build_validation_replay_events
from .daily_market_path_custody import has_reparse_component
from .daily_market_rl_contract import DailyMarketRlContractError

VALIDATION_RECEIPT_FILE = "validation_receipt.json"
VALIDATION_ACTION_LEDGER_FILE = "validation_action_ledger.jsonl"
BUNDLE_MANIFEST_FILE = "bundle_manifest.json"


@dataclass(frozen=True, slots=True)
class AllocationArtifactPaths:
    summary: Path
    receipt: Path
    action_ledger: Path
    telemetry: Path
    bundle_manifest: Path


class AllocationBundleArtifact(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    relative_path: str = Field(min_length=1)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AllocationBundleManifest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_allocation_bundle.v1"]
    research_id: Literal[
        "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001",
        "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002",
    ]
    dataset_id: str
    daily_database_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifacts: tuple[AllocationBundleArtifact, ...]
    historical_test_read: bool
    fresh_oos_read: Literal[False]
    promotion_allowed: Literal[False]


def _write_text(path: Path, value: str) -> None:
    if path.exists():
        raise DailyMarketRlContractError(
            "ALLOCATION_IMMUTABLE_ARTIFACT_ALREADY_EXISTS",
            path.name,
        )
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    if temporary.exists():
        raise DailyMarketRlContractError(
            "ALLOCATION_TEMPORARY_ARTIFACT_ALREADY_EXISTS",
            temporary.name,
        )
    with temporary.open("x", encoding="utf-8", newline="") as handle:
        _ = handle.write(value)
    _ = temporary.rename(path)


def _artifact(path: Path, output_directory: Path) -> AllocationBundleArtifact:
    if has_reparse_component(path) or not path.is_file():
        raise DailyMarketRlContractError(
            "ALLOCATION_BUNDLE_ARTIFACT_UNTRUSTED",
            str(path),
        )
    try:
        relative = path.relative_to(output_directory).as_posix()
    except ValueError as exc:
        raise DailyMarketRlContractError(
            "ALLOCATION_BUNDLE_ARTIFACT_OUTSIDE_RUN",
            str(path),
        ) from exc
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return AllocationBundleArtifact(
        relative_path=relative,
        size_bytes=path.stat().st_size,
        sha256=digest.hexdigest(),
    )


def _artifact_text(relative_path: str, value: str) -> AllocationBundleArtifact:
    payload = value.encode("utf-8")
    return AllocationBundleArtifact(
        relative_path=relative_path,
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def build_allocation_dashboard_summary(
    receipt: AllocationExperimentReceipt,
) -> AllocationDashboardSummary:
    rows = tuple(
        AllocationDashboardRow(
            policy=f"{row.algorithm.value} seed-{row.seed}",
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
            filled_slots=row.validation_base.filled_slots,
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
        historical_test_read=(
            receipt.historical_test_state
            == "FEATURES_PARSED_REWARDS_NOT_READ_CONTAMINATED"
        ),
        promotion_allowed=False,
        fresh_oos_read=False,
        evidence_classification=(
            receipt.lineage.evidence_classification
            if receipt.lineage is not None
            else "LEGACY_EXPLORATORY_CANDIDATE"
        ),
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
    receipt_path = output_directory / VALIDATION_RECEIPT_FILE
    ledger_path = output_directory / VALIDATION_ACTION_LEDGER_FILE
    telemetry_path = output_directory / "rl_live_events.jsonl"
    bundle_manifest_path = output_directory / BUNDLE_MANIFEST_FILE
    summary_text = f"{build_allocation_dashboard_summary(execution.receipt).model_dump_json(indent=2)}\n"
    _write_text(
        receipt_path,
        f"{execution.receipt.model_dump_json(indent=2)}\n",
    )
    ledger = "".join(f"{row.model_dump_json()}\n" for row in execution.trajectories)
    _write_text(ledger_path, ledger)
    events = build_validation_replay_events(
        execution.trajectories,
        median_return_percent=(
            execution.receipt.validation_gate.cql_base_median_return_percent
        ),
    )
    telemetry = "".join(f"{row.model_dump_json()}\n" for row in events)
    _write_text(telemetry_path, telemetry)
    model_paths: list[Path] = []
    for model in execution.receipt.model_runs:
        relative = Path(model.checkpoint_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise DailyMarketRlContractError(
                "ALLOCATION_CHECKPOINT_PATH_INVALID",
                model.checkpoint_path,
            )
        checkpoint = output_directory / relative
        observed = _artifact(checkpoint, output_directory)
        if observed.sha256 != model.checkpoint_sha256:
            raise DailyMarketRlContractError(
                "ALLOCATION_CHECKPOINT_HASH_MISMATCH",
                model.checkpoint_path,
            )
        model_paths.append(checkpoint)
    manifest = AllocationBundleManifest(
        schema_version="kronos_daily_market_allocation_bundle.v1",
        research_id=execution.receipt.research_id,
        dataset_id=execution.receipt.dataset_id,
        daily_database_sha256=execution.receipt.daily_database_sha256,
        artifacts=(
            _artifact_text("summary.json", summary_text),
            *(
                _artifact(path, output_directory)
                for path in (receipt_path, ledger_path, telemetry_path, *model_paths)
            ),
        ),
        historical_test_read=(
            execution.receipt.historical_test_state
            == "FEATURES_PARSED_REWARDS_NOT_READ_CONTAMINATED"
        ),
        fresh_oos_read=False,
        promotion_allowed=False,
    )
    _write_text(
        bundle_manifest_path,
        f"{manifest.model_dump_json(indent=2)}\n",
    )
    _write_text(summary_path, summary_text)
    return AllocationArtifactPaths(
        summary_path,
        receipt_path,
        ledger_path,
        telemetry_path,
        bundle_manifest_path,
    )


__all__ = [
    "AllocationArtifactPaths",
    "AllocationBundleArtifact",
    "AllocationBundleManifest",
    "BUNDLE_MANIFEST_FILE",
    "VALIDATION_ACTION_LEDGER_FILE",
    "VALIDATION_RECEIPT_FILE",
    "build_allocation_dashboard_summary",
    "write_allocation_artifacts",
]
