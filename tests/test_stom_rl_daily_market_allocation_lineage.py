"""Committed-code and preregistration lineage tests for allocation 002."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from stom_rl.daily_market_allocation_experiment_contract import (
    AllocationExperimentReceipt,
)
from stom_rl.daily_market_allocation_lineage import (
    PREREGISTRATION_PATH_TEXT,
    build_registered_allocation_lineage,
)
from stom_rl.daily_market_allocation_lineage_contract import (
    AllocationReproductionEvidence,
)
from stom_rl.daily_market_allocation_run_contract import AllocationInputSnapshot
from stom_rl.daily_market_rl_contract import DailyMarketRlContractError
from tests.daily_market_allocation_fixtures import canonical_allocation_receipt


def _git(repository: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ("git", *arguments),
        cwd=repository,
        check=True,
        capture_output=True,
    ).stdout


def _repository(tmp_path: Path, *, commit_preregistration: bool) -> Path:
    (tmp_path / "stom_rl").mkdir()
    (tmp_path / "docs").mkdir()
    _ = (tmp_path / "stom_rl" / "model.py").write_text("VALUE = 1\n", encoding="utf-8")
    preregistration = tmp_path / PREREGISTRATION_PATH_TEXT
    _ = preregistration.write_text("registered protocol\n", encoding="utf-8")
    _ = _git(tmp_path, "init", "--initial-branch=main")
    _ = _git(tmp_path, "config", "user.email", "lineage@example.invalid")
    _ = _git(tmp_path, "config", "user.name", "Lineage Test")
    _ = _git(tmp_path, "add", "stom_rl")
    if commit_preregistration:
        _ = _git(tmp_path, "add", PREREGISTRATION_PATH_TEXT)
    _ = _git(tmp_path, "commit", "-m", "register lineage fixture")
    return tmp_path


def _snapshot() -> AllocationInputSnapshot:
    return AllocationInputSnapshot(
        rows=(
            ("CANDIDATE_SCORES", "1" * 64),
            ("SOURCE_MANIFEST", "2" * 64),
            ("CAUSAL_PANEL", "3" * 64),
            ("AUTHORITY_RECEIPT", "4" * 64),
            ("SOURCE_ALLOCATION_RECEIPT_001", "5" * 64),
        )
    )


def test_lineage_rejects_an_untracked_preregistration(tmp_path: Path) -> None:
    repository = _repository(tmp_path, commit_preregistration=False)

    with pytest.raises(
        DailyMarketRlContractError,
        match="ALLOCATION_SOURCE_OR_PREREG_NOT_COMMITTED",
    ):
        _ = build_registered_allocation_lineage(_snapshot(), source_root=repository)


@pytest.mark.parametrize("dirty_path", ("stom_rl/model.py", PREREGISTRATION_PATH_TEXT))
def test_lineage_rejects_dirty_source_or_preregistration(
    tmp_path: Path,
    dirty_path: str,
) -> None:
    repository = _repository(tmp_path, commit_preregistration=True)
    with (repository / dirty_path).open("a", encoding="utf-8") as stream:
        _ = stream.write("dirty\n")

    with pytest.raises(
        DailyMarketRlContractError,
        match="ALLOCATION_SOURCE_OR_PREREG_NOT_COMMITTED",
    ):
        _ = build_registered_allocation_lineage(_snapshot(), source_root=repository)


def test_clean_lineage_uses_head_blobs_and_exact_registered_contract(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path, commit_preregistration=True)

    lineage = build_registered_allocation_lineage(_snapshot(), source_root=repository)

    head = _git(repository, "rev-parse", "HEAD").decode().strip()
    tree = _git(repository, "ls-tree", "-rz", "HEAD", "--", "stom_rl")
    preregistration = _git(
        repository,
        "show",
        f"HEAD:{PREREGISTRATION_PATH_TEXT}",
    )
    assert lineage.source_git_sha == head
    assert lineage.source_bundle_sha256 == hashlib.sha256(tree).hexdigest()
    assert lineage.preregistration_sha256 == hashlib.sha256(preregistration).hexdigest()
    assert tuple(row.sha256 for row in lineage.input_hashes) == (
        "1" * 64,
        "2" * 64,
        "3" * 64,
        "4" * 64,
        "5" * 64,
    )
    assert lineage.training.behavior_seeds == tuple(range(1_000, 1_032))
    assert lineage.training.reward_scale == 100.0
    assert lineage.training.target_update_interval == 25


def test_receipt_forbids_001_lineage_and_requires_it_for_002(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path, commit_preregistration=True)
    lineage = build_registered_allocation_lineage(_snapshot(), source_root=repository)
    receipt = canonical_allocation_receipt({})
    legacy_with_lineage = receipt.model_dump(mode="json")
    legacy_with_lineage["lineage"] = lineage.model_dump(mode="json")
    with pytest.raises(ValidationError, match="legacy allocation 001"):
        _ = AllocationExperimentReceipt.model_validate(legacy_with_lineage)

    reproduction = receipt.model_dump(mode="json")
    reproduction["research_id"] = "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002"
    reproduction["authority_research_id"] = "DAILY_MARKET_AUTHORITY_2026_08_10_002"
    reproduction["verdict"] = "REPRODUCTION_ONLY_VALIDATION_CONSUMED"
    reproduction["reasons"] = [
        "VALIDATION_REPRODUCTION_MATCHED_001",
        "VALIDATION_ALREADY_CONSUMED_BY_001",
        *receipt.authority_blockers,
        "HISTORICAL_TEST_FEATURES_ALREADY_CONSUMED_REWARDS_NOT_READ",
        "FRESH_OOS_NOT_RUN_NO_READ",
    ]
    reproduction["historical_test_state"] = (
        "FEATURES_PARSED_REWARDS_NOT_READ_CONTAMINATED"
    )
    with pytest.raises(ValidationError, match="committed lineage"):
        _ = AllocationExperimentReceipt.model_validate(reproduction)
    reproduction["lineage"] = lineage.model_dump(mode="json")
    with pytest.raises(ValidationError, match="reference comparison"):
        _ = AllocationExperimentReceipt.model_validate(reproduction)
    reproduction_evidence = AllocationReproductionEvidence(
        reference_research_id="DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001",
        reference_receipt_sha256="5" * 64,
        reference_evidence_sha256="6" * 64,
        observed_evidence_sha256="6" * 64,
        exact_match=True,
    )
    lineage = lineage.model_copy(update={"reproduction": reproduction_evidence})
    reproduction["lineage"] = lineage.model_dump(mode="json")
    parsed = AllocationExperimentReceipt.model_validate(reproduction)
    assert parsed.lineage == lineage

    mismatch_evidence = reproduction_evidence.model_copy(
        update={
            "observed_evidence_sha256": "7" * 64,
            "exact_match": False,
        }
    )
    mismatch_lineage = lineage.model_copy(update={"reproduction": mismatch_evidence})
    reproduction["lineage"] = mismatch_lineage.model_dump(mode="json")
    reproduction["verdict"] = "REPRODUCTION_MISMATCH_VALIDATION_CONSUMED"
    reproduction["reasons"][0] = "VALIDATION_REPRODUCTION_MISMATCHED_001"

    mismatch = AllocationExperimentReceipt.model_validate(reproduction)

    assert mismatch.verdict == "REPRODUCTION_MISMATCH_VALIDATION_CONSUMED"
