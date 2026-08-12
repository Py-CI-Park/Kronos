"""Immutable small-input snapshots consumed by allocation training."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from collections.abc import Iterator

from .daily_market_allocation_lineage_contract import AllocationLineageInputRole
from .daily_market_allocation_run_contract import (
    AllocationInputSnapshot,
    DailyMarketAllocationPaths,
)
from .daily_market_authority_contract import DailyMarketAuthorityError
from .daily_market_authority_file_custody import copy_stable_file, file_identity
from .daily_market_path_custody import has_reparse_component
from .daily_market_rl_contract import DailyMarketRlContractError


@contextmanager
def immutable_allocation_direct_inputs(
    paths: DailyMarketAllocationPaths,
    expected: AllocationInputSnapshot,
) -> Iterator[DailyMarketAllocationPaths]:
    """Copy each small input once and make loaders consume only those bytes."""
    snapshot_directory = paths.output_directory / "_direct_input_snapshot"
    snapshots: dict[AllocationLineageInputRole, Path] = {}
    sources: dict[AllocationLineageInputRole, Path] = {
        "CANDIDATE_SCORES": paths.candidate_scores,
        "SOURCE_MANIFEST": paths.source_manifest,
        "CAUSAL_PANEL": paths.causal_panel,
        "AUTHORITY_RECEIPT": paths.authority_receipt,
        "SOURCE_ALLOCATION_RECEIPT_001": paths.source_allocation_receipt,
    }
    try:
        snapshot_directory.mkdir(parents=True, exist_ok=False)
        if has_reparse_component(snapshot_directory):
            raise DailyMarketRlContractError("ALLOCATION_SNAPSHOT_OUTPUT_UNTRUSTED")
        for role, expected_sha256 in expected.rows:
            source = sources[role]
            destination = snapshot_directory / source.name
            identity = copy_stable_file(source, destination)
            if identity.sha256 != expected_sha256:
                raise DailyMarketRlContractError(
                    "ALLOCATION_INPUT_CHANGED_DURING_SNAPSHOT",
                    role,
                )
            snapshots[role] = destination
        frozen = replace(
            paths,
            candidate_scores=snapshots["CANDIDATE_SCORES"],
            source_manifest=snapshots["SOURCE_MANIFEST"],
            causal_panel=snapshots["CAUSAL_PANEL"],
            authority_receipt=snapshots["AUTHORITY_RECEIPT"],
            source_allocation_receipt=snapshots["SOURCE_ALLOCATION_RECEIPT_001"],
        )
        yield frozen
        for role, expected_sha256 in expected.rows:
            if file_identity(snapshots[role]).sha256 != expected_sha256:
                raise DailyMarketRlContractError(
                    "ALLOCATION_INPUT_SNAPSHOT_CHANGED_DURING_RUN",
                    role,
                )
    except (OSError, DailyMarketAuthorityError) as exc:
        raise DailyMarketRlContractError("ALLOCATION_INPUT_SNAPSHOT_FAILED") from exc
    finally:
        for snapshot in snapshots.values():
            if snapshot.is_file() and not has_reparse_component(snapshot):
                snapshot.unlink()
        if snapshot_directory.is_dir() and not has_reparse_component(
            snapshot_directory
        ):
            snapshot_directory.rmdir()


__all__ = ["immutable_allocation_direct_inputs"]
