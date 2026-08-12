"""Fail-closed publication validation for the new daily-market research runs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from pydantic import ValidationError

from stom_rl.daily_market_allocation_artifacts import (
    AllocationBundleManifest,
    build_allocation_dashboard_summary,
)
from stom_rl.daily_market_allocation_experiment_contract import (
    AllocationDashboardSummary,
    AllocationExperimentReceipt,
)
from stom_rl.daily_market_allocation_reproduction import (
    allocation_reproduction_projection,
    allocation_reproduction_projection_sha256,
)
from stom_rl.daily_market_authority_artifacts import (
    AuthorityDashboardSummary,
    build_authority_dashboard_summary,
)
from stom_rl.daily_market_authority_contract import (
    DailyMarketAuthorityError,
    MarketAuthorityReceipt,
)
from stom_rl.daily_market_authority_file_custody import (
    file_identity,
    read_stable_file_bytes,
)
from stom_rl.daily_market_path_custody import has_reparse_component
from webui.v6_daily_market_stream_validation import (
    allocation_streams_are_canonical,
)

PublicationState = Literal["NOT_APPLICABLE", "VALID", "INVALID"]
MAX_PUBLICATION_MANIFEST_BYTES: Final = 512 * 1024
MAX_PUBLICATION_JSONL_BYTES: Final = 16 * 1024 * 1024
MODEL_PATH_RE: Final = re.compile(r"^models/(?:CQL|DQN)/seed-[0-4]\.kq$")
ALLOCATION_REQUIRED: Final = frozenset(
    {
        "summary.json",
        "validation_receipt.json",
        "validation_action_ledger.jsonl",
        "rl_live_events.jsonl",
    }
)


@dataclass(frozen=True, slots=True)
class DailyMarketPublication:
    state: PublicationState
    source_file: str | None = None
    summary_bytes: bytes | None = None


def _stable_json(path: Path) -> bytes:
    payload, _identity = read_stable_file_bytes(
        path,
        max_bytes=MAX_PUBLICATION_MANIFEST_BYTES,
    )
    return payload


def _reproduction_is_bound(
    directory: Path,
    receipt: AllocationExperimentReceipt,
) -> bool:
    if receipt.lineage is None or receipt.lineage.reproduction is None:
        return receipt.research_id.endswith("_001")
    evidence = receipt.lineage.reproduction
    observed_sha256 = allocation_reproduction_projection_sha256(
        allocation_reproduction_projection(receipt)
    )
    reference_path = (
        directory.parent / evidence.reference_research_id / "validation_receipt.json"
    )
    try:
        reference_payload, reference_identity = read_stable_file_bytes(
            reference_path,
            max_bytes=MAX_PUBLICATION_MANIFEST_BYTES,
        )
        reference = AllocationExperimentReceipt.model_validate_json(reference_payload)
    except (OSError, ValidationError, DailyMarketAuthorityError):
        return False
    reference_sha256 = allocation_reproduction_projection_sha256(
        allocation_reproduction_projection(reference)
    )
    return (
        reference.research_id == evidence.reference_research_id
        and reference_identity.sha256 == evidence.reference_receipt_sha256
        and reference_sha256 == evidence.reference_evidence_sha256
        and observed_sha256 == evidence.observed_evidence_sha256
    )


def _allocation_publication(directory: Path) -> DailyMarketPublication:
    manifest_path = directory / "bundle_manifest.json"
    footprint = (
        directory.name.startswith("DAILY_MARKET_ALLOCATION_SCREEN_")
        or manifest_path.exists()
        or (directory / "validation_receipt.json").exists()
    )
    if not footprint:
        return DailyMarketPublication("NOT_APPLICABLE")
    if has_reparse_component(manifest_path) or not manifest_path.is_file():
        return DailyMarketPublication("INVALID")
    try:
        manifest = AllocationBundleManifest.model_validate_json(
            _stable_json(manifest_path)
        )
    except (OSError, ValidationError, DailyMarketAuthorityError):
        return DailyMarketPublication("INVALID")
    if manifest.research_id != directory.name:
        return DailyMarketPublication("INVALID")
    declared = tuple(row.relative_path for row in manifest.artifacts)
    if len(declared) != 14 or len(set(declared)) != len(declared):
        return DailyMarketPublication("INVALID")
    declared_set = set(declared)
    if not ALLOCATION_REQUIRED.issubset(declared_set):
        return DailyMarketPublication("INVALID")
    model_paths = declared_set - ALLOCATION_REQUIRED
    if len(model_paths) != 10 or any(
        MODEL_PATH_RE.fullmatch(path) is None for path in model_paths
    ):
        return DailyMarketPublication("INVALID")
    direct_payloads: dict[str, bytes] = {}
    for artifact in manifest.artifacts:
        relative = Path(artifact.relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            return DailyMarketPublication("INVALID")
        path = directory / relative
        try:
            if artifact.relative_path in {
                "summary.json",
                "validation_receipt.json",
                "validation_action_ledger.jsonl",
                "rl_live_events.jsonl",
            }:
                payload, observed = read_stable_file_bytes(
                    path,
                    max_bytes=(
                        MAX_PUBLICATION_MANIFEST_BYTES
                        if artifact.relative_path.endswith(".json")
                        else MAX_PUBLICATION_JSONL_BYTES
                    ),
                )
                direct_payloads[artifact.relative_path] = payload
            else:
                observed = file_identity(path)
        except (OSError, DailyMarketAuthorityError):
            return DailyMarketPublication("INVALID")
        if (
            observed.size_bytes != artifact.size_bytes
            or observed.sha256 != artifact.sha256
        ):
            return DailyMarketPublication("INVALID")
    try:
        receipt = AllocationExperimentReceipt.model_validate_json(
            direct_payloads["validation_receipt.json"]
        )
        summary = AllocationDashboardSummary.model_validate_json(
            direct_payloads["summary.json"]
        )
    except (KeyError, ValidationError):
        return DailyMarketPublication("INVALID")
    expected_model_hashes = {
        model.checkpoint_path: model.checkpoint_sha256 for model in receipt.model_runs
    }
    manifest_model_hashes = {
        artifact.relative_path: artifact.sha256
        for artifact in manifest.artifacts
        if MODEL_PATH_RE.fullmatch(artifact.relative_path) is not None
    }
    if (
        receipt.research_id != directory.name
        or manifest.dataset_id != receipt.dataset_id
        or manifest.daily_database_sha256 != receipt.daily_database_sha256
        or manifest_model_hashes != expected_model_hashes
        or summary != build_allocation_dashboard_summary(receipt)
        or not _reproduction_is_bound(directory, receipt)
        or not allocation_streams_are_canonical(
            receipt,
            direct_payloads["validation_action_ledger.jsonl"],
            direct_payloads["rl_live_events.jsonl"],
        )
    ):
        return DailyMarketPublication("INVALID")
    return DailyMarketPublication(
        "VALID", "summary.json", direct_payloads["summary.json"]
    )


def _authority_publication(directory: Path) -> DailyMarketPublication:
    receipt_path = directory / "authority_receipt.json"
    summary_path = directory / "summary.json"
    footprint = receipt_path.exists() or directory.name.startswith(
        "DAILY_MARKET_AUTHORITY_"
    )
    if not footprint:
        return DailyMarketPublication("NOT_APPLICABLE")
    if any(
        has_reparse_component(path) or not path.is_file()
        for path in (receipt_path, summary_path)
    ):
        return DailyMarketPublication("INVALID")
    try:
        receipt = MarketAuthorityReceipt.model_validate_json(_stable_json(receipt_path))
        summary_bytes = _stable_json(summary_path)
        summary = AuthorityDashboardSummary.model_validate_json(summary_bytes)
    except (OSError, ValidationError, DailyMarketAuthorityError):
        return DailyMarketPublication("INVALID")
    if (
        receipt.research_id != directory.name
        or summary != build_authority_dashboard_summary(receipt)
    ):
        return DailyMarketPublication("INVALID")
    return DailyMarketPublication("VALID", "summary.json", summary_bytes)


def observe_daily_market_publication(directory: Path) -> DailyMarketPublication:
    allocation = _allocation_publication(directory)
    if allocation.state != "NOT_APPLICABLE":
        return allocation
    return _authority_publication(directory)


def daily_market_publication_state(directory: Path) -> PublicationState:
    return observe_daily_market_publication(directory).state


__all__ = [
    "DailyMarketPublication",
    "PublicationState",
    "daily_market_publication_state",
    "observe_daily_market_publication",
]
