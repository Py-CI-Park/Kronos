"""Detached HMAC approval for exact D5S Smoke evidence."""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d3_approval import smoke_approval_signature
from stom_rl.rl_discovery.d5_approval import primary_custody_signature
from stom_rl.rl_discovery.d5s_contract import load_d5s_prereg_bytes
from stom_rl.rl_discovery.storage import RunDirectoryGuard, artifact_manifest_sha256


class _FrozenBoundary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)


class _SmokeModel(_FrozenBoundary):
    reward_arm: Literal["NATIVE", "SHUFFLED"]
    seed: Literal[0]
    total_steps: Literal[4096]
    fit_23bp: dict[str, float | int]
    native_23bp: dict[str, float | int]
    native_0bp: dict[str, float | int]


class _SmokeSummary(_FrozenBoundary):
    schema_version: Literal["kronos.rl-discovery.d5s.stability.v1"]
    profile: Literal["SMOKE"]
    status: Literal["COMPLETE"]
    verdict: Literal["D5S_SMOKE_COMPLETE"]
    gate: None
    models: tuple[_SmokeModel, ...]
    source_run: Literal["type2-d5r-primary-20260730-001"]
    approved_smoke: None
    d5_verdict_unchanged: Literal["D5_FULL_TRAIN_COST_NOT_CONFIRMED"]
    d5r_verdict_unchanged: Literal["D5R_CAPACITY_NOT_CONFIRMED"]
    reused_validation: Literal["NOT_RUN_NO_READ"]
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    promotion_allowed: Literal[False]
    profitability_claim_allowed: Literal[False]
    live_broker_order_allowed: Literal[False]


class _SmokeReceipt(_FrozenBoundary):
    schema_version: Literal["kronos.rl-discovery.d5s.receipt.v1"]
    profile: Literal["SMOKE"]
    status: Literal["COMPLETE"]
    verdict: Literal["D5S_SMOKE_COMPLETE"]
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    live_broker_order_allowed: Literal[False]


class _OperatorApproval(_FrozenBoundary):
    kind: Literal["D5S_SMOKE_OPERATOR_APPROVAL_V1"]
    run_name: str = Field(min_length=1)
    prereg_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    episode_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_hmac_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class D5SApprovalError(PermissionError):
    """D5S Smoke is incomplete, mismatched, or unauthenticated."""


def create_d5s_smoke_approval(path: Path, *, run_root: Path, approval_key: bytes) -> Path:
    if len(approval_key) < 32:
        raise D5SApprovalError("D5S Smoke approval requires a 32-byte key")
    guard = RunDirectoryGuard.capture(run_root, path)
    prereg_sha, episode_sha, manifest_sha = _verified_smoke(guard)
    approval = {
        "kind": "D5S_SMOKE_OPERATOR_APPROVAL_V1",
        "run_name": path.name,
        "prereg_sha256": prereg_sha,
        "episode_snapshot_sha256": episode_sha,
        "artifact_manifest_sha256": manifest_sha,
        "approval_hmac_sha256": smoke_approval_signature(
            approval_key,
            run_name=path.name,
            prereg_sha=prereg_sha,
            episode_sha=episode_sha,
            manifest_sha=manifest_sha,
        ),
    }
    return guard.publish_bytes(canonical_json_bytes(approval), "operator_approval.json")


def approve_d5s_smoke(
    path: Path | None,
    *,
    run_root: Path,
    approval_key: bytes | None,
    prereg_sha: str,
    episode_sha: str,
) -> str:
    if path is None or approval_key is None or len(approval_key) < 32:
        raise D5SApprovalError("D5S Primary requires detached Smoke approval")
    guard = RunDirectoryGuard.capture(run_root, path)
    observed_prereg, observed_episode, manifest_sha = _verified_smoke(guard)
    approval = _OperatorApproval.model_validate_json((path / "operator_approval.json").read_bytes())
    expected = smoke_approval_signature(
        approval_key,
        run_name=path.name,
        prereg_sha=prereg_sha,
        episode_sha=episode_sha,
        manifest_sha=manifest_sha,
    )
    if (
        observed_prereg != prereg_sha
        or observed_episode != episode_sha
        or approval.run_name != path.name
        or approval.prereg_sha256 != prereg_sha
        or approval.episode_snapshot_sha256 != episode_sha
        or approval.artifact_manifest_sha256 != manifest_sha
        or not hmac.compare_digest(approval.approval_hmac_sha256, expected)
    ):
        raise D5SApprovalError("D5S Smoke approval identity is mismatched")
    return path.name


def _verified_smoke(guard: RunDirectoryGuard) -> tuple[str, str, str]:
    root = guard.verify()
    summary = _SmokeSummary.model_validate_json((root / "summary.json").read_bytes())
    receipt = _SmokeReceipt.model_validate_json((root / "terminal_receipt.json").read_bytes())
    if {(row.reward_arm, row.seed, row.total_steps) for row in summary.models} != {
        ("NATIVE", 0, 4096),
        ("SHUFFLED", 0, 4096),
    }:
        raise D5SApprovalError("D5S Smoke requires the exact two-unit matrix")
    expected_files = {
        root / "models" / arm / "seed-0" / "steps-4096" / "model.zip"
        for arm in ("NATIVE", "SHUFFLED")
    } | {
        root / "outcomes" / arm / "seed-0" / "steps-4096.json"
        for arm in ("NATIVE", "SHUFFLED")
    }
    if not all(path.is_file() for path in expected_files):
        raise D5SApprovalError("D5S Smoke model or outcome artifacts are incomplete")
    manifest_sha = artifact_manifest_sha256(
        root,
        excluded_relative_paths=frozenset({"terminal_receipt.json", "operator_approval.json"}),
    )
    if receipt.artifact_manifest_sha256 != manifest_sha:
        raise D5SApprovalError("D5S Smoke artifact manifest is mismatched")
    prereg_bytes = (root / "inputs" / "prereg.json").read_bytes()
    prereg = load_d5s_prereg_bytes(prereg_bytes)
    return hashlib.sha256(prereg_bytes).hexdigest(), prereg.source_run.episode_snapshot_sha256, manifest_sha


__all__ = ["approve_d5s_smoke", "create_d5s_smoke_approval", "primary_custody_signature"]
