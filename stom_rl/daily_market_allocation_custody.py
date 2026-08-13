"""Immutable input and output custody for the allocation screen runner."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import ValidationError

from .daily_market_allocation_run_contract import (
    AllocationInputSnapshot,
    DailyMarketAllocationPaths,
)
from .daily_market_allocation_lineage_contract import AllocationLineageInputRole
from .daily_market_authority_bound_sources import (
    bound_current_metadata,
    bound_pit_records,
    bound_price_provenance,
)
from .daily_market_authority_contract import (
    DailyMarketAuthorityError,
    MarketAuthorityReceipt,
    SIGNED_SOURCE_REVIEW_SUPPORTED,
)
from .daily_market_authority_file_custody import file_identity
from .daily_market_path_custody import has_reparse_component
from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_stockinfo_authority import observe_stockinfo_authority


def _authority_input_paths(paths: DailyMarketAllocationPaths) -> dict[str, Path]:
    return {
        "DAILY_DATABASE": paths.daily_database,
        "STOCKINFO_DATABASE": paths.stockinfo_database,
        "CANDIDATE_SCORES": paths.candidate_scores,
        "PRICE_PROVENANCE": paths.price_provenance,
        "CURRENT_OFFICIAL_METADATA": paths.current_official_metadata,
        "PIT_MEMBERSHIP": paths.pit_membership,
    }


def _verify_authority_bindings(
    paths: DailyMarketAllocationPaths,
    receipt: MarketAuthorityReceipt,
) -> None:
    expected_paths = _authority_input_paths(paths)
    bindings = {binding.role: binding for binding in receipt.input_bindings}
    if len(bindings) != len(receipt.input_bindings) or set(bindings) != set(
        expected_paths
    ):
        raise DailyMarketRlContractError("ALLOCATION_AUTHORITY_BINDINGS_INVALID")
    for role, path in expected_paths.items():
        binding = bindings[role]
        if binding.state == "MISSING":
            if path.exists():
                raise DailyMarketRlContractError(
                    "ALLOCATION_AUTHORITY_INPUT_CHANGED",
                    role,
                )
            continue
        if binding.state == "INVALID":
            if path.exists() and path.is_file() and not has_reparse_component(path):
                raise DailyMarketRlContractError(
                    "ALLOCATION_AUTHORITY_INPUT_CHANGED",
                    role,
                )
            continue
        if binding.identity is None:
            raise DailyMarketRlContractError("ALLOCATION_AUTHORITY_BINDINGS_INVALID")
        try:
            observed = (
                observe_stockinfo_authority(path).identity
                if role == "STOCKINFO_DATABASE"
                else file_identity(path)
            )
        except (OSError, DailyMarketAuthorityError) as exc:
            raise DailyMarketRlContractError(
                "ALLOCATION_AUTHORITY_INPUT_UNREADABLE",
                role,
            ) from exc
        if observed != binding.identity:
            raise DailyMarketRlContractError(
                "ALLOCATION_AUTHORITY_INPUT_CHANGED",
                role,
            )
    for identity in receipt.source_artifacts:
        if identity.path_suffix != f"{identity.sha256}.source":
            raise DailyMarketRlContractError("ALLOCATION_AUTHORITY_SOURCE_INVALID")
        source = paths.source_artifact_root / identity.path_suffix
        try:
            observed = file_identity(source)
        except (OSError, DailyMarketAuthorityError) as exc:
            raise DailyMarketRlContractError(
                "ALLOCATION_AUTHORITY_SOURCE_UNREADABLE",
                identity.path_suffix,
            ) from exc
        if observed != identity:
            raise DailyMarketRlContractError(
                "ALLOCATION_AUTHORITY_SOURCE_CHANGED",
                identity.path_suffix,
            )


def _verify_verified_source_set(
    paths: DailyMarketAllocationPaths,
    receipt: MarketAuthorityReceipt,
) -> None:
    if receipt.status != "VERIFIED_RESEARCH_DATA_AUTHORITY":
        return
    bindings = {binding.role: binding for binding in receipt.input_bindings}
    provenance_state, provenance, provenance_binding = bound_price_provenance(
        paths.price_provenance
    )
    current_state, current_hashes, current_binding = bound_current_metadata(
        paths.current_official_metadata
    )
    pit_state, pit_rows, pit_binding = bound_pit_records(paths.pit_membership)
    observed_bindings = {
        "PRICE_PROVENANCE": provenance_binding,
        "CURRENT_OFFICIAL_METADATA": current_binding,
        "PIT_MEMBERSHIP": pit_binding,
    }
    if any(bindings[role] != binding for role, binding in observed_bindings.items()):
        raise DailyMarketRlContractError("ALLOCATION_AUTHORITY_INPUT_CHANGED")
    if (
        provenance_state != "PRESENT"
        or provenance is None
        or current_state != "PRESENT"
        or pit_state != "PRESENT"
        or provenance.database_sha256 != receipt.daily_database.sha256
    ):
        raise DailyMarketRlContractError("ALLOCATION_AUTHORITY_VERDICT_INCONSISTENT")
    declared_hashes = {
        provenance.source_sha256,
        *current_hashes,
        *(row.source_hash for row in pit_rows),
    }
    receipt_hashes = {identity.sha256 for identity in receipt.source_artifacts}
    if not declared_hashes or receipt_hashes != declared_hashes:
        raise DailyMarketRlContractError("ALLOCATION_AUTHORITY_SOURCE_SET_MISMATCH")


def load_allocation_authority(
    paths: DailyMarketAllocationPaths,
) -> MarketAuthorityReceipt:
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
    if (
        receipt.status == "VERIFIED_RESEARCH_DATA_AUTHORITY"
        and not SIGNED_SOURCE_REVIEW_SUPPORTED
    ):
        raise DailyMarketRlContractError(
            "ALLOCATION_AUTHORITY_SIGNED_REVIEW_UNSUPPORTED"
        )
    _verify_authority_bindings(paths, receipt)
    _verify_verified_source_set(paths, receipt)
    if receipt.status == "VERIFIED_RESEARCH_DATA_AUTHORITY" and (
        receipt.blockers
        or receipt.d0_price_basis.state != "VERIFIED"
        or receipt.d1_universe.state != "VERIFIED"
    ):
        raise DailyMarketRlContractError("ALLOCATION_AUTHORITY_VERDICT_INCONSISTENT")
    daily_binding = next(
        binding
        for binding in receipt.input_bindings
        if binding.role == "DAILY_DATABASE"
    )
    if daily_binding.identity != receipt.daily_database:
        raise DailyMarketRlContractError("ALLOCATION_DATABASE_AUTHORITY_HASH_MISMATCH")
    return receipt


def capture_allocation_input_snapshot(
    paths: DailyMarketAllocationPaths,
) -> AllocationInputSnapshot:
    direct_inputs: tuple[tuple[AllocationLineageInputRole, Path], ...] = (
        ("CANDIDATE_SCORES", paths.candidate_scores),
        ("SOURCE_MANIFEST", paths.source_manifest),
        ("CAUSAL_PANEL", paths.causal_panel),
        ("AUTHORITY_RECEIPT", paths.authority_receipt),
        ("SOURCE_ALLOCATION_RECEIPT_001", paths.source_allocation_receipt),
    )
    try:
        rows: list[tuple[AllocationLineageInputRole, str]] = []
        for role, path in direct_inputs:
            rows.append((role, file_identity(path).sha256))
    except (OSError, DailyMarketAuthorityError) as exc:
        raise DailyMarketRlContractError("ALLOCATION_INPUT_SNAPSHOT_FAILED") from exc
    return AllocationInputSnapshot(rows=tuple(rows))


def assert_allocation_inputs_unchanged(
    paths: DailyMarketAllocationPaths,
    expected: AllocationInputSnapshot,
) -> None:
    observed = capture_allocation_input_snapshot(paths)
    if observed != expected:
        raise DailyMarketRlContractError("ALLOCATION_INPUT_CHANGED_DURING_RUN")


def ensure_allocation_output_available(output_directory: Path) -> None:
    if has_reparse_component(output_directory):
        raise DailyMarketRlContractError("ALLOCATION_OUTPUT_UNTRUSTED")
    if output_directory.exists():
        if not output_directory.is_dir():
            raise DailyMarketRlContractError("ALLOCATION_OUTPUT_UNTRUSTED")
        if next(output_directory.iterdir(), None) is not None:
            raise DailyMarketRlContractError("ALLOCATION_OUTPUT_ALREADY_EXISTS")


@contextmanager
def immutable_allocation_database_snapshot(
    paths: DailyMarketAllocationPaths,
    expected_sha256: str,
) -> Iterator[Path]:
    """Copy the audited DB once and train only from that isolated byte snapshot."""
    snapshot_directory = paths.output_directory / "_input_snapshot"
    snapshot = snapshot_directory / f"{expected_sha256}.db"
    try:
        snapshot_directory.mkdir(parents=True, exist_ok=False)
        if has_reparse_component(snapshot_directory):
            raise DailyMarketRlContractError("ALLOCATION_SNAPSHOT_OUTPUT_UNTRUSTED")
        _ = shutil.copyfile(paths.daily_database, snapshot)
        if file_identity(snapshot).sha256 != expected_sha256:
            raise DailyMarketRlContractError(
                "ALLOCATION_DATABASE_SNAPSHOT_HASH_MISMATCH"
            )
        if file_identity(paths.daily_database).sha256 != expected_sha256:
            raise DailyMarketRlContractError(
                "ALLOCATION_DATABASE_CHANGED_DURING_SNAPSHOT"
            )
        yield snapshot
        try:
            final_snapshot_hash = file_identity(snapshot).sha256
        except (OSError, DailyMarketAuthorityError) as exc:
            raise DailyMarketRlContractError(
                "ALLOCATION_DATABASE_SNAPSHOT_CHANGED_DURING_RUN"
            ) from exc
        if final_snapshot_hash != expected_sha256:
            raise DailyMarketRlContractError(
                "ALLOCATION_DATABASE_SNAPSHOT_CHANGED_DURING_RUN"
            )
    finally:
        if snapshot.is_file() and not has_reparse_component(snapshot):
            snapshot.unlink()
        if snapshot_directory.is_dir() and not has_reparse_component(
            snapshot_directory
        ):
            snapshot_directory.rmdir()


__all__ = [
    "assert_allocation_inputs_unchanged",
    "capture_allocation_input_snapshot",
    "ensure_allocation_output_available",
    "immutable_allocation_database_snapshot",
    "load_allocation_authority",
]
