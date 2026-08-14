"""Create-exclusive artifacts for the existing-DB historical simulation."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from .daily_market_existing_db_sim_contract import (
    ExistingDbSimulationArtifactRecord,
    ExistingDbSimulationBundleManifest,
    ExistingDbSimulationReceipt,
    ExistingDbSimulationStep,
    ExistingDbSimulationSummary,
    SimulationArtifactName,
)
from .daily_market_path_custody import has_reparse_component
from .daily_market_rl_contract import DailyMarketRlContractError


@dataclass(frozen=True, slots=True)
class ExistingDbSimulationArtifactPaths:
    summary: Path
    receipt: Path
    ledger: Path
    bundle_manifest: Path


def _write_exclusive(path: Path, payload: bytes) -> None:
    with path.open("xb") as handle:
        _ = handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _identity(path: Path) -> ExistingDbSimulationArtifactRecord:
    payload = path.read_bytes()
    return ExistingDbSimulationArtifactRecord(
        path=cast(SimulationArtifactName, path.name),
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def write_existing_db_simulation_artifacts(
    receipt: ExistingDbSimulationReceipt,
    steps: tuple[ExistingDbSimulationStep, ...],
    output_directory: Path,
) -> ExistingDbSimulationArtifactPaths:
    """Publish receipt, summary, ledger and a hash manifest without overwrite."""
    if has_reparse_component(output_directory) or output_directory.exists():
        raise DailyMarketRlContractError("HISTORICAL_SIMULATION_OUTPUT_UNTRUSTED")
    output_directory.mkdir(parents=True, exist_ok=False)
    paths = ExistingDbSimulationArtifactPaths(
        summary=output_directory / "summary.json",
        receipt=output_directory / "simulation_receipt.json",
        ledger=output_directory / "action_ledger.jsonl",
        bundle_manifest=output_directory / "bundle_manifest.json",
    )
    summary = ExistingDbSimulationSummary(
        schema_version="kronos_existing_db_60_historical_summary.v1",
        research_id=receipt.research_id,
        verdict=receipt.verdict,
        status=receipt.status,
        research_scope="POST_HOC_EXISTING_DB_HISTORICAL_SIMULATION",
        window_start="2026-03-09",
        window_end="2026-06-11",
        requested_score_days=receipt.window.requested_score_days,
        available_reward_days=receipt.window.available_reward_days,
        non_overlapping_decisions=receipt.window.non_overlapping_decisions,
        technical_gate_passed=receipt.gate.technical_gate_passed,
        cql_base_median_return_percent=receipt.gate.cql_base_median_return_percent,
        cql_stress_median_return_percent=receipt.gate.cql_stress_median_return_percent,
        best_base_control_return_percent=receipt.gate.best_base_control_return_percent,
        failed_checks=receipt.gate.failed_checks,
        future_data_used=False,
        independent_oos_claim_allowed=False,
        promotion_allowed=False,
        paper_live_allowed=False,
    )
    _write_exclusive(
        paths.summary,
        f"{summary.model_dump_json(indent=2)}\n".encode("utf-8"),
    )
    _write_exclusive(
        paths.receipt,
        f"{receipt.model_dump_json(indent=2)}\n".encode("utf-8"),
    )
    ledger = b"".join(f"{step.model_dump_json()}\n".encode("utf-8") for step in steps)
    _write_exclusive(paths.ledger, ledger)
    manifest = ExistingDbSimulationBundleManifest(
        schema_version="kronos_existing_db_60_historical_bundle.v1",
        research_id=receipt.research_id,
        artifacts=(
            _identity(paths.summary),
            _identity(paths.receipt),
            _identity(paths.ledger),
        ),
        artifact_count=3,
        ledger_row_count=len(steps),
        complete=True,
    )
    _write_exclusive(
        paths.bundle_manifest,
        f"{manifest.model_dump_json(indent=2)}\n".encode("utf-8"),
    )
    return paths


__all__ = [
    "ExistingDbSimulationArtifactPaths",
    "write_existing_db_simulation_artifacts",
]
