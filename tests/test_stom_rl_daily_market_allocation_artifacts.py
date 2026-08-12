"""Immutable publication tests for the daily-market allocation bundle."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from stom_rl.daily_market_allocation_artifacts import (
    AllocationBundleManifest,
    write_allocation_artifacts,
)
from stom_rl.daily_market_rl_contract import DailyMarketRlContractError
from tests.daily_market_allocation_fixtures import canonical_allocation_execution


def test_writer_publishes_exact_hash_bound_bundle_with_summary_last(
    tmp_path: Path,
) -> None:
    execution = canonical_allocation_execution(tmp_path)

    paths = write_allocation_artifacts(execution, tmp_path)

    manifest = AllocationBundleManifest.model_validate_json(
        paths.bundle_manifest.read_bytes()
    )
    assert len(manifest.artifacts) == 14
    assert len({row.relative_path for row in manifest.artifacts}) == 14
    for artifact in manifest.artifacts:
        payload = (tmp_path / artifact.relative_path).read_bytes()
        assert len(payload) == artifact.size_bytes
        assert hashlib.sha256(payload).hexdigest() == artifact.sha256
    assert paths.summary.is_file()


def test_writer_rejects_checkpoint_tamper_before_completion_marker(
    tmp_path: Path,
) -> None:
    execution = canonical_allocation_execution(tmp_path)
    checkpoint = tmp_path / execution.receipt.model_runs[0].checkpoint_path
    _ = checkpoint.write_bytes(b"tampered")

    with pytest.raises(
        DailyMarketRlContractError,
        match="ALLOCATION_CHECKPOINT_HASH_MISMATCH",
    ):
        _ = write_allocation_artifacts(execution, tmp_path)

    assert not (tmp_path / "bundle_manifest.json").exists()
    assert not (tmp_path / "summary.json").exists()


@pytest.mark.parametrize("preexisting", ("bundle_manifest.json", "summary.json"))
def test_writer_never_overwrites_a_preexisting_completion_artifact(
    tmp_path: Path,
    preexisting: str,
) -> None:
    execution = canonical_allocation_execution(tmp_path)
    _ = (tmp_path / preexisting).write_text("preserve-me", encoding="utf-8")

    with pytest.raises(
        DailyMarketRlContractError,
        match="ALLOCATION_IMMUTABLE_ARTIFACT_ALREADY_EXISTS",
    ):
        _ = write_allocation_artifacts(execution, tmp_path)

    assert (tmp_path / preexisting).read_text(encoding="utf-8") == "preserve-me"
