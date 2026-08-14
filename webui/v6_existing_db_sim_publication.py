"""Fail-closed publication validation for the existing-DB simulation bundle."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from stom_rl.daily_market_authority_contract import DailyMarketAuthorityError
from stom_rl.daily_market_authority_file_custody import read_stable_file_bytes
from stom_rl.daily_market_existing_db_sim_contract import (
    ExistingDbSimulationBundleManifest,
    ExistingDbSimulationReceipt,
    ExistingDbSimulationStep,
    ExistingDbSimulationSummary,
)
from stom_rl.daily_market_path_custody import has_reparse_component

ExistingDbPublicationState = Literal["NOT_APPLICABLE", "VALID", "INVALID"]
MAX_JSON_BYTES = 512 * 1024
MAX_LEDGER_BYTES = 2 * 1024 * 1024
EXPECTED_MANIFEST_SHA256 = (
    "ca8f837bc4b8148405f2e576a12326a91c6c800479c3390efea559bacd41b6b6"
)


def _invalid() -> tuple[ExistingDbPublicationState, str | None, bytes | None]:
    return "INVALID", None, None


def observe_existing_db_simulation_publication(
    directory: Path,
) -> tuple[ExistingDbPublicationState, str | None, bytes | None]:
    """Return valid summary bytes only when every immutable artifact is bound."""
    footprint = directory.name.startswith("DAILY_MARKET_EXISTING_DB_60_SIM_")
    if not footprint:
        return "NOT_APPLICABLE", None, None
    paths = {
        "bundle_manifest.json": directory / "bundle_manifest.json",
        "summary.json": directory / "summary.json",
        "simulation_receipt.json": directory / "simulation_receipt.json",
        "action_ledger.jsonl": directory / "action_ledger.jsonl",
    }
    if any(
        has_reparse_component(path) or not path.is_file() for path in paths.values()
    ):
        return _invalid()
    try:
        manifest_bytes, manifest_identity = read_stable_file_bytes(
            paths["bundle_manifest.json"], max_bytes=MAX_JSON_BYTES
        )
        summary_bytes, summary_identity = read_stable_file_bytes(
            paths["summary.json"], max_bytes=MAX_JSON_BYTES
        )
        receipt_bytes, receipt_identity = read_stable_file_bytes(
            paths["simulation_receipt.json"], max_bytes=MAX_JSON_BYTES
        )
        ledger_bytes, ledger_identity = read_stable_file_bytes(
            paths["action_ledger.jsonl"], max_bytes=MAX_LEDGER_BYTES
        )
        manifest = ExistingDbSimulationBundleManifest.model_validate_json(
            manifest_bytes
        )
        summary = ExistingDbSimulationSummary.model_validate_json(summary_bytes)
        receipt = ExistingDbSimulationReceipt.model_validate_json(receipt_bytes)
    except (OSError, ValidationError, DailyMarketAuthorityError):
        return _invalid()
    if manifest_identity.sha256 != EXPECTED_MANIFEST_SHA256:
        return _invalid()
    observed = {
        "summary.json": summary_identity,
        "simulation_receipt.json": receipt_identity,
        "action_ledger.jsonl": ledger_identity,
    }
    if any(
        observed[artifact.path].size_bytes != artifact.size_bytes
        or observed[artifact.path].sha256 != artifact.sha256
        for artifact in manifest.artifacts
    ):
        return _invalid()
    try:
        lines = tuple(line for line in ledger_bytes.splitlines() if line)
        steps = tuple(
            ExistingDbSimulationStep.model_validate_json(line) for line in lines
        )
    except ValidationError:
        return _invalid()
    metric_keys = {
        (metric.policy, metric.policy_kind, metric.seed, metric.scenario)
        for metric in receipt.metrics
    }
    step_counts = Counter(
        (step.policy, step.policy_kind, step.seed, step.scenario) for step in steps
    )
    expected_count = receipt.window.non_overlapping_decisions
    if (
        manifest.research_id != directory.name
        or summary.research_id != receipt.research_id
        or receipt.research_id != manifest.research_id
        or len(receipt.metrics) != 34
        or len(receipt.checkpoint_identities) != 5
        or manifest.ledger_row_count != len(steps)
        or len(steps) != 34 * expected_count
        or set(step_counts) != metric_keys
        or any(count != expected_count for count in step_counts.values())
        or summary.technical_gate_passed != receipt.gate.technical_gate_passed
        or summary.cql_base_median_return_percent
        != receipt.gate.cql_base_median_return_percent
        or summary.cql_stress_median_return_percent
        != receipt.gate.cql_stress_median_return_percent
        or summary.best_base_control_return_percent
        != receipt.gate.best_base_control_return_percent
        or summary.failed_checks != receipt.gate.failed_checks
        or summary.available_reward_days != receipt.window.available_reward_days
        or summary.non_overlapping_decisions != receipt.window.non_overlapping_decisions
    ):
        return _invalid()
    return "VALID", "summary.json", summary_bytes


__all__ = ["observe_existing_db_simulation_publication"]
