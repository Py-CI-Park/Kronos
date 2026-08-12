"""Build the committed preregistration and code lineage for allocation 002."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Literal

from .daily_market_allocation_lineage_contract import (
    AllocationInputHash,
    AllocationLineageEvidence,
    AllocationTrainingEvidence,
)
from .daily_market_allocation_run_contract import AllocationInputSnapshot
from .daily_market_rl_contract import BEHAVIOR_SEEDS, DailyMarketRlContractError

PREREGISTRATION_PATH_TEXT: Literal[
    "docs/kronos_v1_29_0_market_authority_allocation_prereg_002_2026-08-10.md"
] = "docs/kronos_v1_29_0_market_authority_allocation_prereg_002_2026-08-10.md"


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise DailyMarketRlContractError(
            "ALLOCATION_LINEAGE_GIT_FAILED",
            completed.stderr.strip(),
        )
    return completed.stdout.strip()


def _git_bytes(repository: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repository,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise DailyMarketRlContractError(
            "ALLOCATION_LINEAGE_GIT_FAILED",
            completed.stderr.decode("utf-8", errors="replace").strip(),
        )
    return completed.stdout


def _committed_source_identity(source_root: Path) -> tuple[str, str, str]:
    source_sha = _git(source_root, "rev-parse", "HEAD")
    tracked = subprocess.run(
        (
            "git",
            "ls-files",
            "--error-unmatch",
            "--",
            PREREGISTRATION_PATH_TEXT,
        ),
        cwd=source_root,
        check=False,
        capture_output=True,
    )
    if tracked.returncode != 0:
        raise DailyMarketRlContractError("ALLOCATION_SOURCE_OR_PREREG_NOT_COMMITTED")
    status = _git(
        source_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        "stom_rl",
        PREREGISTRATION_PATH_TEXT,
    )
    if status:
        raise DailyMarketRlContractError("ALLOCATION_SOURCE_OR_PREREG_NOT_COMMITTED")
    tree = _git_bytes(source_root, "ls-tree", "-rz", "HEAD", "--", "stom_rl")
    preregistration = _git_bytes(
        source_root,
        "show",
        f"HEAD:{PREREGISTRATION_PATH_TEXT}",
    )
    return (
        source_sha,
        hashlib.sha256(tree).hexdigest(),
        hashlib.sha256(preregistration).hexdigest(),
    )


def build_registered_allocation_lineage(
    input_snapshot: AllocationInputSnapshot,
    *,
    source_root: Path | None = None,
) -> AllocationLineageEvidence:
    observed_source_root = (
        source_root.resolve()
        if source_root is not None
        else Path(__file__).resolve().parents[1]
    )
    source_git_sha, source_bundle_sha256, preregistration_sha256 = (
        _committed_source_identity(observed_source_root)
    )
    return AllocationLineageEvidence(
        evidence_classification="POST_HOC_CUSTODY_REPRODUCTION",
        preregistration_path=PREREGISTRATION_PATH_TEXT,
        preregistration_sha256=preregistration_sha256,
        source_git_sha=source_git_sha,
        source_bundle_sha256=source_bundle_sha256,
        input_hashes=tuple(
            AllocationInputHash(role=role, sha256=sha256)
            for role, sha256 in input_snapshot.rows
        ),
        training=AllocationTrainingEvidence(
            model_seeds=(0, 1, 2, 3, 4),
            behavior_seeds=BEHAVIOR_SEEDS,
            behavior_policy="UNIFORM_RANDOM_FOUR_ACTIONS_TRAIN_ONLY",
            input_dimension=172,
            action_count=4,
            hidden_dimensions=(128, 64),
            learning_rate=0.0003,
            discount=0.95,
            dqn_cql_alpha=0.0,
            cql_cql_alpha=1.0,
            reward_scale=100.0,
            batch_size=256,
            gradient_steps=600,
            target_update_interval=25,
        ),
    )


__all__ = ["build_registered_allocation_lineage"]
